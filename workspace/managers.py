"""
Custom QuerySets = tumhari business language ORM me.
`Task.objects.for_org("acme").open().overdue()` padhne me query jaisa nahi,
domain jaisa lagta hai - aur har jagah copy-paste filters nahi likhne padte.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.enums import TaskStatus
from core.managers import SoftDeleteQuerySet


class TaskQuerySet(SoftDeleteQuerySet):
    def for_org(self, slug: str):
        return self.filter(project__organization__slug=slug)

    def open(self):
        return self.filter(status__in=TaskStatus.open_statuses())

    def overdue(self):
        return self.open().filter(due_date__lt=timezone.localdate())

    def assigned_to(self, user):
        return self.filter(assignee=user)

    def high_priority(self):
        return self.filter(priority__gte=3)

    def with_logged_minutes(self):
        # Sirf ek reverse FK aggregate hai isliye JOIN safe hai.
        # Do alag reverse FKs aggregate karoge toh fan-out se numbers galat honge
        # -> tab Subquery use karo (selectors.py dekho).
        return self.annotate(
            logged_minutes=Coalesce(Sum("time_entries__minutes"), Value(0)),
            entry_count=Count("time_entries", distinct=True),
        )

    def with_overrun(self):
        """F() = column-to-column comparison, DB me hota hai, Python me nahi."""
        return self.with_logged_minutes().annotate(
            estimate_minutes=F("estimate_hours") * 60,
            overrun_minutes=Case(
                When(logged_minutes__gt=F("estimate_hours") * 60,
                     then=F("logged_minutes") - F("estimate_hours") * 60),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )

    def search(self, term: str):
        if not term:
            return self
        # Q objects = composable boolean logic (| & ~)
        return self.filter(Q(title__icontains=term) | Q(description__icontains=term))


class TaskManager(models.Manager.from_queryset(TaskQuerySet)):
    """
    from_queryset() = QuerySet ke saare methods manager pe bhi mil jaate hain.
    get_queryset() override karke default scope (alive only) lagate hain.

    GOTCHA: ye scope sirf `Task.objects` aur reverse accessor (project.tasks)
    pe lagta hai. JOIN traversal (`filter(task__project=...)`) _base_manager
    use karta hai - wahan deleted_at filter khud lagana padega.
    """

    def get_queryset(self):
        return super().get_queryset().alive()
