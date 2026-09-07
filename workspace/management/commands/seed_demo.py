"""
Custom management command = tumhara CLI script jise Django ka full context milta hai.
    python manage.py seed_demo --orgs 2 --tasks 40 --flush

Cron/CI/one-off backfill sab isi pattern se.
"""
from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.enums import Priority, Role, TaskStatus
from core.types import SeedPlan
from core.utils import chunked
from workspace.models import (Membership, Organization, Project, Task, TimeEntry)

User = get_user_model()
FIRST = ["Aarav", "Isha", "Kabir", "Meera", "Rohan", "Sara", "Vikram", "Nisha"]
LAST = ["Rao", "Nair", "Sethi", "Bose", "Iyer", "Malik"]


class Command(BaseCommand):
    help = "Seed demo workspace data."

    def add_arguments(self, parser):
        parser.add_argument("--orgs", type=int, default=1)
        parser.add_argument("--projects", type=int, default=3)
        parser.add_argument("--tasks", type=int, default=25)
        parser.add_argument("--entries", type=int, default=4)
        parser.add_argument("--seed", type=int, default=42, help="RNG seed (reproducible)")
        parser.add_argument("--flush", action="store_true", help="Purana data delete karo")

    @transaction.atomic  # poora seed ek transaction me - beech me fail hua toh clean rollback
    def handle(self, *args, **opts):
        if opts["tasks"] < 1:
            raise CommandError("--tasks 1 se zyada hona chahiye")

        random.seed(opts["seed"])
        plan = SeedPlan(
            orgs=opts["orgs"], projects_per_org=opts["projects"],
            tasks_per_project=opts["tasks"], entries_per_task=opts["entries"],
        )

        if opts["flush"]:
            TimeEntry.objects.all().delete()
            Task.all_objects.all().delete()
            Project.all_objects.all().hard_delete()
            Membership.objects.all().delete()
            Organization.objects.all().delete()
            self.stdout.write(self.style.WARNING("flushed existing data"))

        users = self._make_users(12)
        now = timezone.now()
        total_entries = 0

        for o in range(plan.orgs):
            org = Organization.objects.create(name=f"Org {o + 1}")
            Membership.objects.bulk_create([
                Membership(organization=org, user=u,
                           role=Role.OWNER if i == 0 else random.choice([Role.MANAGER, Role.MEMBER]))
                for i, u in enumerate(users)
            ])

            for p in range(plan.projects_per_org):
                project = Project.objects.create(
                    organization=org, code=f"P{o + 1}{p + 1:02d}",
                    name=f"{random.choice(['Atlas', 'Nova', 'Orbit', 'Quartz'])} {p + 1}",
                    budget_hours=Decimal(random.choice([80, 120, 200, 320])),
                )

                tasks = Task.objects.bulk_create(
                    self._task_stream(project, users, plan.tasks_per_project, now),
                    batch_size=200,
                )
                # bulk_create signals fire nahi karta - isliye seed ke baad
                # rollup command chalana zaroori hai. Ye trade-off yaad rakho.

                entries = list(self._entry_stream(tasks, users, plan.entries_per_task, now))
                for batch in chunked(entries, 500):   # generator -> memory flat
                    TimeEntry.objects.bulk_create(batch)
                total_entries += len(entries)

        self.stdout.write(self.style.SUCCESS(
            f"seeded: {Organization.objects.count()} orgs, {Project.objects.count()} projects, "
            f"{Task.all_objects.count()} tasks, {total_entries} time entries"
        ))
        self.stdout.write("login: owner@example.com / demo12345")

    # ---- helpers (generators - list banate nahi, stream karte hain) ----
    def _make_users(self, n: int) -> list:
        users = []
        for i in range(n):
            email = "owner@example.com" if i == 0 else f"user{i}@example.com"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"full_name": f"{random.choice(FIRST)} {random.choice(LAST)}"},
            )
            if created:
                user.set_password("demo12345")
                user.is_staff = i == 0
                user.is_superuser = i == 0
                user.save(update_fields=["password", "is_staff", "is_superuser"])
            users.append(user)
        return users

    def _task_stream(self, project, users, count, now):
        for i in range(count):
            status = random.choices(
                [TaskStatus.BACKLOG, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.DONE],
                weights=[3, 3, 1, 4],
            )[0]
            yield Task(
                project=project,
                title=f"{random.choice(['Fix', 'Build', 'Refactor', 'Ship'])} module {i + 1}",
                status=status,
                completed_at=now - timedelta(days=random.randint(0, 10)) if status == TaskStatus.DONE else None,
                priority=random.choice(list(Priority.values)),
                assignee=random.choice(users),
                estimate_hours=Decimal(random.choice([2, 4, 8, 16])),
                due_date=(now + timedelta(days=random.randint(-10, 20))).date(),
            )

    def _entry_stream(self, tasks, users, per_task, now):
        for task in tasks:
            for _ in range(random.randint(0, per_task)):
                yield TimeEntry(
                    task=task,
                    user=task.assignee or random.choice(users),
                    started_at=now - timedelta(days=random.randint(0, 13), hours=random.randint(0, 8)),
                    minutes=random.choice([25, 45, 60, 90, 120, 180]),
                    note=random.choice(["", "pairing", "review", "debugging"]),
                )
