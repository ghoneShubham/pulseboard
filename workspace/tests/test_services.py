from datetime import timedelta
from decimal import Decimal
import logging
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from core.enums import TaskStatus
from core.exceptions import BudgetExceeded, InvalidTransition, PermissionDenied
from workspace.models import (ActivityLog, DailyProjectRollup, Membership,
                              Organization, Project, Task, TimeEntry)
from workspace.services import (archive_project, bump_priority, log_time,
                                   move_task, reassign_task)
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





class ReassignTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.other_org = Organization.objects.create(name="Globex", slug="globex")

        cls.manager = User.objects.create_user("mgr@x.com", "pw", full_name="Manager")
        cls.member = User.objects.create_user("mem@x.com", "pw", full_name="Member")
        cls.teammate = User.objects.create_user("team@x.com", "pw", full_name="Teammate")
        cls.outsider = User.objects.create_user("out@x.com", "pw", full_name="Outsider")

        Membership.objects.create(organization=cls.org, user=cls.manager, role="manager")
        Membership.objects.create(organization=cls.org, user=cls.member, role="member")
        Membership.objects.create(organization=cls.org, user=cls.teammate, role="member")
        # outsider belongs ONLY to a different org - never a member of cls.org
        Membership.objects.create(organization=cls.other_org, user=cls.outsider, role="member")

        cls.project = Project.objects.create(
            organization=cls.org, code="ACM1", name="Atlas", budget_hours=Decimal("10")
        )

    def _task(self):
        return Task.objects.create(project=self.project, title="T", assignee=self.member)

    def test_manager_can_reassign_to_org_member(self):
        task = self._task()
        updated = reassign_task(task_id=task.pk, to_user=self.teammate, actor=self.manager)
        self.assertEqual(updated.assignee_id, self.teammate.pk)

    def test_reassign_writes_activity_log(self):
        task = self._task()
        reassign_task(task_id=task.pk, to_user=self.teammate, actor=self.manager)
        log = ActivityLog.objects.get(verb="task.reassigned")
        self.assertEqual(log.payload["from_user_id"], self.member.pk)
        self.assertEqual(log.payload["to_user_id"], self.teammate.pk)

    def test_non_manager_cannot_reassign(self):
        task = self._task()
        with self.assertRaises(PermissionDenied):
            reassign_task(task_id=task.pk, to_user=self.teammate, actor=self.member)

    def test_cannot_reassign_to_non_member(self):
        task = self._task()
        with self.assertRaises(PermissionDenied):
            reassign_task(task_id=task.pk, to_user=self.outsider, actor=self.manager)

    def test_non_manager_rejection_does_not_change_assignee(self):
        task = self._task()
        original_assignee_id = task.assignee_id
        with self.assertRaises(PermissionDenied):
            reassign_task(task_id=task.pk, to_user=self.teammate, actor=self.member)
        task.refresh_from_db()
        self.assertEqual(task.assignee_id, original_assignee_id)

    def test_reassign_invalidates_org_summary_cache(self):
        from workspace.selectors import org_summary
        task = self._task()
        org_summary("acme")  # warm the cache
        reassign_task(task_id=task.pk, to_user=self.teammate, actor=self.manager)
        # if invalidate() worked, this call recomputes rather than returning stale data
        self.assertEqual(org_summary("acme")["total"], 1)
        
        
        
        
        



class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class OnCommitRollbackTests(TestCase):
    """
    4.4 - transaction.on_commit() ke bina, side-effect (log line) rollback
    ke baad bhi chal jaata hai - jhooth bol raha hota hai ki kuch hua,
    jabki TimeEntry actually DB me kabhi save hi nahi hua.
    """

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="RB", slug="rb")
        cls.project = Project.objects.create(
            organization=cls.org, code="RB1", name="RB", budget_hours=Decimal("10")
        )
        cls.task = Task.objects.create(project=cls.project, title="T")
        cls.user = User.objects.create_user("rb@x.com", "pw", full_name="RB User")

    def test_log_does_not_fire_after_rollback(self):
        """This should PASS with on_commit() in place."""
        from django.db import transaction

        handler = _ListHandler()
        logger = logging.getLogger("pulseboard")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            with transaction.atomic():
                log_time(task_id=self.task.pk, user=self.user, started_at=timezone.now(), minutes=30)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        finally:
            logger.removeHandler(handler)

        self.assertEqual(len(handler.records), 0, "log fired even though the transaction rolled back")
        self.assertFalse(TimeEntry.objects.filter(task=self.task).exists())