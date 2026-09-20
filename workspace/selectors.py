"""
SELECTORS = read side. Saara ORM knowledge yahan hai.
Views patle rehte hain, aur ye functions test karna trivial hai.

Prisma se aa rahe ho toh mapping:
  select_related      ~ include (JOIN, forward FK/OneToOne)
  prefetch_related    ~ include (2nd query, M2M/reverse FK)
  annotate            ~ computed field per row
  aggregate           ~ groupBy ka scalar result
  Subquery/OuterRef   ~ correlated subquery (Prisma me raw SQL lagti hai)
"""
from __future__ import annotations

from datetime import date, timedelta

from django.db.models import (
    Avg, Case, CharField, Count, DecimalField, DurationField, Exists, F,
    IntegerField, OuterRef, Prefetch, Q, QuerySet, Subquery, Sum, Value,
    When, Window,
)

from django.db.models.functions import Coalesce, DenseRank, Rank, TruncDate
from django.utils import timezone

from core.decorators import cached_for, timed
from core.enums import Health, TaskStatus
from core.types import BurndownPoint, ContributorRow, ProjectHealth
from core.utils import daterange

from .models import ActivityLog, Organization, Project, Task, TimeEntry


# ---------------------------------------------------------------- N+1 ka ilaaj
def project_list(org_slug: str) -> QuerySet[Project]:
    """
    select_related  -> forward FK, SQL JOIN, 1 query
    prefetch_related-> reverse FK/M2M, alag query + Python join
    Prefetch()      -> prefetched queryset ko filter/order karne ke liye
    """
    open_tasks = Task.objects.open().select_related("assignee").order_by("-priority")
    return (
        Project.objects.filter(organization__slug=org_slug)
        .select_related("organization")
        .prefetch_related(Prefetch("tasks", queryset=open_tasks, to_attr="open_tasks"))
    )


# ------------------------------------------------- Subquery vs JOIN fan-out
def _logged_minutes_sq():
    """
    Do reverse-FK aggregates ek saath karoge toh rows duplicate ho jaati hain
    aur Sum inflate ho jaata hai. Subquery se har aggregate apne scope me rehta hai.
    """
    return (
        TimeEntry.objects.filter(task__project=OuterRef("pk"))
        .values("task__project")
        .annotate(total=Sum("minutes"))
        .values("total")[:1]
    )


def _open_task_count_sq():
    return (
        Task.objects.filter(project=OuterRef("pk"), deleted_at__isnull=True)
        .filter(status__in=TaskStatus.open_statuses())
        .values("project")
        .annotate(n=Count("id"))
        .values("n")[:1]
    )


def project_health(org_slug: str) -> list[ProjectHealth]:
    today = timezone.localdate()

    overdue_exists = Task.objects.filter(
        project=OuterRef("pk"), due_date__lt=today, deleted_at__isnull=True
    ).exclude(status=TaskStatus.DONE)

    qs = (
        Project.objects.filter(organization__slug=org_slug)
        .annotate(
            logged_minutes=Coalesce(Subquery(_logged_minutes_sq(), output_field=IntegerField()), 0),
            open_tasks=Coalesce(Subquery(_open_task_count_sq(), output_field=IntegerField()), 0),
            has_overdue=Exists(overdue_exists),
            avg_cycle_time=Avg(
                F("tasks__completed_at") - F("tasks__created_at"),
                filter=Q(tasks__status=TaskStatus.DONE),
                output_field=DurationField(),
            ),
        )
        # Alag annotate() call - kyunki pichhli annotation ko yahan reference kar rahe hain
        .annotate(
            health=Case(
                When(budget_hours=0, then=Value(str(Health.HEALTHY))),
                When(logged_minutes__gt=F("budget_hours") * 60, then=Value(str(Health.OVER_BUDGET))),
                When(logged_minutes__gte=F("budget_hours") * 48, then=Value(str(Health.AT_RISK))),
                default=Value(str(Health.HEALTHY)),
                output_field=CharField(),
            )
        )
        .order_by("code")
    )
    # dataclass me convert - baaki app ko QuerySet ki leak nahi milti
    return [
        ProjectHealth(
            project_id=p.pk, code=p.code, name=p.name, budget_hours=p.budget_hours,
            logged_minutes=p.logged_minutes, open_tasks=p.open_tasks,
            health=str(p.health), has_overdue=p.has_overdue,
            avg_cycle_time=p.avg_cycle_time or timedelta(0), 

        )
        for p in qs
    ]


# --------------------------------------------------------- window functions
def top_contributors(project_id: int, limit: int = 5) -> list[ContributorRow]:
    """
    values() + annotate() = GROUP BY.
    Window(Rank()) = RANK() OVER (...) - aggregate ke upar ranking bina 2nd query.
    """
    rows = (
        TimeEntry.objects.filter(task__project_id=project_id)
        .values("user_id", "user__full_name")
        .annotate(total_minutes=Sum("minutes"))
        .annotate(rank=Window(expression=DenseRank(), order_by=F("total_minutes").desc()))
        .order_by("rank")[:limit]
    )
    return [
        ContributorRow(
            user_id=r["user_id"], full_name=r["user__full_name"],
            total_minutes=r["total_minutes"], rank=r["rank"],
        )
        for r in rows
    ]


def running_effort(user_id: int, project_id: int):
    """PARTITION BY - per-user cumulative total, ek hi query me."""
    return (
        TimeEntry.objects.filter(user_id=user_id, task__project_id=project_id)
        .annotate(
            cumulative=Window(
                expression=Sum("minutes"),
                partition_by=[F("user_id")],
                order_by=F("started_at").asc(),
            )
        )
        .values("started_at", "minutes", "cumulative")
        .order_by("started_at")
    )


# ------------------------------------------------ date truncation + gap fill
@timed
def burndown(project_id: int, days: int = 14) -> list[BurndownPoint]:
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)

    grouped = (
        TimeEntry.objects.filter(task__project_id=project_id, started_at__date__gte=start)
        .annotate(day=TruncDate("started_at"))
        .values("day")
        .annotate(minutes=Sum("minutes"))
        .order_by("day")
    )
    by_day: dict[date, int] = {row["day"]: row["minutes"] for row in grouped}

    points: list[BurndownPoint] = []
    total = 0
    for day in daterange(start, end):  # generator - missing days fill
        minutes = by_day.get(day, 0)
        total += minutes
        points.append(BurndownPoint(day=day, minutes=minutes, cumulative_minutes=total))
    return points


# ------------------------------------------------------------- aggregate()
@cached_for(60, key_prefix="v1:")
def org_summary(org_slug: str) -> dict:
    """
    JOIN FAN-OUT KA CLASSIC TRAP:

        Task.objects.for_org(slug).aggregate(
            total=Count("id"),
            logged=Sum("time_entries__minutes"),   # <-- ye JOIN add karta hai
        )

    time_entries ka JOIN har task ki row ko N baar duplicate kar deta hai,
    to Count("id") inflate ho jaata hai (humare seed pe 90 -> 189).
    Ilaaj: ya toh Count(distinct=True), ya - behtar - alag-alag aggregate.

    aggregate() ek dict return karta hai (queryset nahi).
    filter= argument conditional aggregation deta hai, alag query ke bina.
    Result 60s cache me; write ke baad org_summary.invalidate(slug) call karo.
    """
    task_stats = Task.objects.for_org(org_slug).aggregate(
        total=Count("id"),
        done=Count("id", filter=Q(status=TaskStatus.DONE)),
        blocked=Count("id", filter=Q(status=TaskStatus.BLOCKED)),
        avg_estimate=Coalesce(Avg("estimate_hours"), Value(0), output_field=DecimalField()),
    )
    logged = TimeEntry.objects.filter(
        task__project__organization__slug=org_slug, task__deleted_at__isnull=True
    ).aggregate(total=Coalesce(Sum("minutes"), Value(0)))["total"]

    return {**task_stats, "logged_minutes": logged}


def recent_activity(project: Project, limit: int = 10):
    return (
        ActivityLog.objects.filter(
            content_type__model="project", object_id=project.pk
        ).select_related("actor")[:limit]
    )


def organizations_for(user) -> QuerySet[Organization]:
    return Organization.objects.filter(memberships__user=user).distinct()
