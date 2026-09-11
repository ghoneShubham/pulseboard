"""
TaskQuerySet ke chainable methods ke tests.
Manager pe method likhoge toh chain toot jaati hai - isiliye QuerySet pe
likha hai aur from_queryset() se Manager banaya hai. Ye test confirm karta
hai ki chaining kaam karti hai.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.enums import TaskStatus
from workspace.models import Membership, Organization, Project, Task

User = get_user_model()


class TaskQuerySetStaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.alice = User.objects.create_user("a@x.com", "pw", full_name="Alice")
        Membership.objects.create(organization=cls.org, user=cls.alice, role="owner")

        cls.project = Project.objects.create(
            organization=cls.org, code="ACM1", name="Atlas", budget_hours=Decimal("10")
        )

        cls.fresh_task = Task.objects.create(
            project=cls.project,
            title="Fresh open task",
            status=TaskStatus.IN_PROGRESS,
            priority=4,
        )

        cls.stale_task = Task.objects.create(
            project=cls.project,
            title="Stale open task",
            status=TaskStatus.IN_PROGRESS,
            priority=4,
        )
        Task.objects.filter(pk=cls.stale_task.pk).update(
            updated_at=timezone.now() - timedelta(days=10)
        )

        cls.stale_done_task = Task.objects.create(
            project=cls.project,
            title="Stale done task",
            status=TaskStatus.DONE,
            completed_at=timezone.now(),
            priority=4,
        )
        Task.objects.filter(pk=cls.stale_done_task.pk).update(
            updated_at=timezone.now() - timedelta(days=10)
        )

    def test_stale_excludes_fresh_open_task(self):
        result = Task.objects.stale()
        self.assertNotIn(self.fresh_task, result)

    def test_stale_includes_old_open_task(self):
        result = Task.objects.stale()
        self.assertIn(self.stale_task, result)

    def test_stale_excludes_old_done_task(self):
        result = Task.objects.stale()
        self.assertNotIn(self.stale_done_task, result)

    def test_stale_chains_with_for_org_and_high_priority(self):
        result = Task.objects.for_org("acme").stale().high_priority()
        self.assertIn(self.stale_task, result)
        self.assertNotIn(self.fresh_task, result)