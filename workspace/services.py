"""
SERVICES = write side. Har state change yahan se guzarta hai.

Kyun? Business rule ek jagah rahe - API, admin, management command aur
Celery task sab isi function ko call karein. Model.save() me logic thoosne se
bulk operations use bypass kar dete hain.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, F, Sum
from django.utils import timezone
from django.db.models.functions import TruncDate

from core.enums import Role, TaskStatus
from core.exceptions import BudgetExceeded, InvalidTransition, PermissionDenied
from core.types import SupportsAudit

from .models import (ActivityLog, DailyProjectRollup, Membership, Organization,
                     Project, Task, TimeEntry)
from .selectors import org_summary

logger = logging.getLogger("pulseboard")

# Simple state machine - dict of allowed transitions
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TaskStatus.BACKLOG: {TaskStatus.IN_PROGRESS},
    TaskStatus.IN_PROGRESS: {TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.BACKLOG},
    TaskStatus.BLOCKED: {TaskStatus.IN_PROGRESS},
    TaskStatus.DONE: set(),  # terminal
}


def record_activity(actor, verb: str, target: SupportsAudit, **payload) -> ActivityLog:
    return ActivityLog.objects.create(
        actor=actor,
        verb=verb,
        content_type=ContentType.objects.get_for_model(target.__class__),
        object_id=target.pk,
        payload=payload,
    )


def _assert_can_manage(user, organization: Organization) -> Membership:
    membership = Membership.objects.filter(user=user, organization=organization).first()
    if membership is None:
        raise PermissionDenied("You are not a member of this organization.")
    if not Role(membership.role).can_manage:
        raise PermissionDenied("Manager role required.", required_role="manager")
    return membership


@transaction.atomic
def move_task(*, task_id: int, to_status: str, actor) -> Task:
    """
    select_for_update() = SELECT ... FOR UPDATE, row lock jab tak transaction chale.
    Do parallel requests same task move karein toh race nahi hogi.
    NOTE: lock sirf transaction ke andar kaam karta hai (isliye atomic zaroori hai).
    """
    task = Task.objects.select_for_update().select_related("project__organization").get(pk=task_id)

    if to_status not in ALLOWED_TRANSITIONS[task.status]:
        raise InvalidTransition(
            f"Cannot move from {task.status} to {to_status}.",
            allowed=sorted(ALLOWED_TRANSITIONS[task.status]),
        )

    previous, task.status = task.status, to_status
    task.completed_at = timezone.now() if to_status == TaskStatus.DONE else None
    task.save(update_fields=["status", "completed_at", "updated_at"])

    record_activity(actor, "task.moved", task, **{"from": previous, "to": to_status})
    org_summary.invalidate(task.project.organization.slug)  # cache stale na rahe
    return task


@transaction.atomic
def log_time(*, task_id: int, user, started_at: datetime, minutes: int, note: str = "") -> TimeEntry:
    task = Task.objects.select_related("project").get(pk=task_id)

    if not task.is_open:
        raise InvalidTransition("Cannot log time on a closed task.", task_id=task_id)

    budget_minutes = int(task.project.budget_hours * 60)
    if budget_minutes:
        # Denormalized counter - Project.logged_minutes - instead of a live
        # Sum() over every TimeEntry every single time. O(1) read vs O(n).
        # Trade-off: this number can drift from reality if it's ever updated
        # outside this function (bulk edits, direct SQL, a bug in another
        # code path) - there's no DB constraint tying it back to the real
        # sum of TimeEntry.minutes for this project.
        logged = task.project.logged_minutes
        if logged + minutes > budget_minutes * Decimal("1.2"):
            raise BudgetExceeded(
                "Logging this entry would blow the project budget by >20%.",
                budget_minutes=budget_minutes, logged_minutes=logged,
            )

    entry = TimeEntry.objects.create(
        task=task, user=user, started_at=started_at, minutes=minutes, note=note
    )

    # F() update - race-free even if two log_time() calls run concurrently.
    Project.objects.filter(pk=task.project_id).update(logged_minutes=F("logged_minutes") + minutes)

    transaction.on_commit(lambda: logger.info("time logged: entry=%s", entry.pk))
    #causes failing test 
    #logger.info("time logged: entry=%s", entry.pk)

    record_activity(user, "time.logged", task, minutes=minutes)
    org_summary.invalidate(task.project.organization.slug)
    return entry


@transaction.atomic
def bump_priority(*, task_ids: list[int], by: int = 1) -> int:
    """
    F() expression = update DB me hota hai, ek query me, race-free.
    Galat tarika: obj.priority += 1; obj.save()  (read-modify-write race)
    """
    return Task.objects.filter(pk__in=task_ids, priority__lt=4).update(
        priority=F("priority") + by, updated_at=timezone.now()
    )





@transaction.atomic
def reassign_task(*, task_id: int, to_user, actor) -> Task:
    """
    Rules: sirf manager reassign kar sakta hai; naya assignee usi org ka
    member hona chahiye; activity log; cache invalidate.
    """
    task = Task.objects.select_related("project__organization").get(pk=task_id)
    organization = task.project.organization

    _assert_can_manage(actor, organization)  # sirf manager/owner

    is_member = Membership.objects.filter(user=to_user, organization=organization).exists()
    if not is_member:
        raise PermissionDenied(
            "New assignee must be a member of this organization.",
            organization=organization.slug,
        )

    previous_assignee_id = task.assignee_id
    task.assignee = to_user
    task.save(update_fields=["assignee", "updated_at"])

    record_activity(
        actor, "task.reassigned", task,
        **{"from_user_id": previous_assignee_id, "to_user_id": to_user.pk},
    )
    org_summary.invalidate(organization.slug)
    return task

@transaction.atomic
def archive_project(*, project_id: int, actor) -> Project:
    project = Project.objects.select_related("organization").get(pk=project_id)
    _assert_can_manage(actor, project.organization)

    project.is_archived = True
    project.save(update_fields=["is_archived", "updated_at"])
    Task.objects.filter(project=project).open().delete()  # soft delete (queryset override)

    record_activity(actor, "project.archived", project)
    org_summary.invalidate(project.organization.slug)
    return project


def rebuild_rollups(*, days: int, project_id: int | None = None,
                    organization_id: int | None = None) -> int:
    """Upsert DailyProjectRollup rows for the last `days` days. Returns row count."""
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)

    qs = TimeEntry.objects.filter(started_at__date__gte=start)
    if project_id:
        qs = qs.filter(task__project_id=project_id)
    if organization_id:
        qs = qs.filter(task__project__organization_id=organization_id)

    rows = (
        qs.annotate(day=TruncDate("started_at"))
        .values("task__project_id", "day")
        .annotate(
            minutes=Sum("minutes"),
            entries=Count("id"),
            contributors=Count("user_id", distinct=True),
        )
        .order_by()
    )
    objects = [
        DailyProjectRollup(
            project_id=r["task__project_id"], day=r["day"],
            minutes=r["minutes"], entries=r["entries"], contributors=r["contributors"],
        )
        for r in rows
    ]
    with transaction.atomic():
        DailyProjectRollup.objects.bulk_create(
            objects,
            update_conflicts=True,
            update_fields=["minutes", "entries", "contributors"],
            unique_fields=["project", "day"],
            batch_size=500,
        )
    return len(objects)


def trigger_rollup(*, actor, org_slug: str, days: int) -> int:
    """Owner-only, org-scoped rebuild. Non-member and non-owner get the SAME error,
    so the response doesn't reveal whether an org slug exists."""
    membership = (
        Membership.objects.select_related("organization")
        .filter(user=actor, organization__slug=org_slug)
        .first()
    )
    if membership is None or membership.role != Role.OWNER:
        raise PermissionDenied("Only the organization owner can rebuild rollups.",
                               required_role="owner")
    org = membership.organization
    count = rebuild_rollups(days=days, organization_id=org.pk)
    record_activity(actor, "rollup.rebuilt", org, days=days, rows=count)
    return count
