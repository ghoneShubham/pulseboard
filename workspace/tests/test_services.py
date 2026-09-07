from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.enums import TaskStatus
from core.exceptions import BudgetExceeded, InvalidTransition, PermissionDenied
from workspace.models import (ActivityLog, DailyProjectRollup, Membership,
                              Organization, Project, Task, TimeEntry)
from workspace.services import archive_project, bump_priority, log_time, move_task

User = get_user_model()


class ServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.owner = User.objects.create_user("o@x.com", "pw", full_name="Owner")
        cls.member = User.objects.create_user("m@x.com", "pw", full_name="Member")
        Membership.objects.create(organization=cls.org, user=cls.owner, role="owner")
        Membership.objects.create(organization=cls.org, user=cls.member, role="member")
        cls.project = Project.objects.create(
            organization=cls.org, code="ACM1", name="Atlas", budget_hours=Decimal("2")
        )

    def _task(self, status=TaskStatus.BACKLOG):
        return Task.objects.create(project=self.project, title="T", status=status)

    def test_valid_transition_writes_activity(self):
        task = self._task()
        moved = move_task(task_id=task.pk, to_status=TaskStatus.IN_PROGRESS, actor=self.owner)
        self.assertEqual(moved.status, TaskStatus.IN_PROGRESS)
        self.assertTrue(ActivityLog.objects.filter(verb="task.moved").exists())

    def test_invalid_transition_blocked(self):
        task = self._task()
        with self.assertRaises(InvalidTransition):
            move_task(task_id=task.pk, to_status=TaskStatus.DONE, actor=self.owner)

    def test_done_sets_completed_at(self):
        task = self._task(TaskStatus.IN_PROGRESS)
        moved = move_task(task_id=task.pk, to_status=TaskStatus.DONE, actor=self.owner)
        self.assertIsNotNone(moved.completed_at)

    def test_budget_guard(self):
        task = self._task(TaskStatus.IN_PROGRESS)
        log_time(task_id=task.pk, user=self.owner, started_at=timezone.now(), minutes=120)
        with self.assertRaises(BudgetExceeded):
            log_time(task_id=task.pk, user=self.owner, started_at=timezone.now(), minutes=60)

    def test_cannot_log_on_closed_task(self):
        task = self._task(TaskStatus.IN_PROGRESS)
        move_task(task_id=task.pk, to_status=TaskStatus.DONE, actor=self.owner)
        with self.assertRaises(InvalidTransition):
            log_time(task_id=task.pk, user=self.owner, started_at=timezone.now(), minutes=30)

    def test_member_cannot_archive(self):
        with self.assertRaises(PermissionDenied):
            archive_project(project_id=self.project.pk, actor=self.member)

    def test_archive_soft_deletes_open_tasks(self):
        self._task(TaskStatus.IN_PROGRESS)
        archive_project(project_id=self.project.pk, actor=self.owner)
        self.assertEqual(Task.objects.filter(project=self.project).count(), 0)
        self.assertEqual(Task.all_objects.filter(project=self.project).count(), 1)

    def test_bump_priority_uses_single_update_query(self):
        ids = [self._task().pk for _ in range(3)]
        # SAVEPOINT + UPDATE + RELEASE = 3. Asli baat: N tasks pe bhi
        # sirf EK UPDATE - Python loop hota toh N queries lagti.
        with self.assertNumQueries(3):
            bump_priority(task_ids=ids)
        self.assertTrue(all(p == 3 for p in Task.objects.filter(pk__in=ids).values_list("priority", flat=True)))


class RollupCommandTests(TestCase):
    def test_rollup_is_idempotent_upsert(self):
        org = Organization.objects.create(name="Acme", slug="acme")
        user = User.objects.create_user("u@x.com", "pw")
        project = Project.objects.create(organization=org, code="A1", name="A")
        task = Task.objects.create(project=project, title="T")
        now = timezone.now()
        TimeEntry.objects.create(task=task, user=user, started_at=now, minutes=45)
        TimeEntry.objects.create(task=task, user=user, started_at=now - timedelta(days=1), minutes=30)

        call_command("daily_rollup", "--days", "7", verbosity=0)
        call_command("daily_rollup", "--days", "7", verbosity=0)  # dobara - duplicate nahi

        self.assertEqual(DailyProjectRollup.objects.count(), 2)
        self.assertEqual(DailyProjectRollup.objects.order_by("-day").first().minutes, 45)
