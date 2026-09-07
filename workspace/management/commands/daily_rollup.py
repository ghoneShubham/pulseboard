"""
Nightly aggregation job.
    python manage.py daily_rollup --days 14

Ye BullMQ worker ka Django-side equivalent hai. Production me isko
Celery beat / cron se chalate hain; logic yahin rehta hai taaki
manually bhi run kar sako aur test bhi.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.context_managers import stopwatch
from workspace.models import DailyProjectRollup, Project, TimeEntry


class Command(BaseCommand):
    help = "Rebuild DailyProjectRollup for the last N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--project", type=int, default=None)

    def handle(self, *args, **opts):
        end = timezone.localdate()
        start = end - timedelta(days=opts["days"] - 1)

        qs = TimeEntry.objects.filter(started_at__date__gte=start)
        if opts["project"]:
            qs = qs.filter(task__project_id=opts["project"])

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

        verbose = opts.get("verbosity", 1)
        with stopwatch("rollup", enabled=verbose > 0), transaction.atomic():
            # UPSERT - Django 4.1+. Pehle delete-then-insert karna padta tha,
            # jo race-prone tha aur PK churn karta tha.
            DailyProjectRollup.objects.bulk_create(
                objects,
                update_conflicts=True,
                update_fields=["minutes", "entries", "contributors"],
                unique_fields=["project", "day"],
                batch_size=500,
            )

        if verbose:
            self.stdout.write(self.style.SUCCESS(f"{len(objects)} rollup rows upserted ({start} -> {end})"))
