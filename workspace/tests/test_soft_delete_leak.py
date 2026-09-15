"""
Soft-delete leak test.

Task.objects (TaskManager) correctly hides soft-deleted tasks for direct
queries. But that filtering happens in TaskManager.get_queryset() - which
is only consulted for `Task.objects.*` and the reverse accessor
(`project.tasks.*`, which Django wires to the model's default manager).

A JOIN *through* the relation (e.g. filtering Project by a lookup that
crosses into Task, like `tasks__id=...` or `tasks__status=...`) does NOT
go through TaskManager at all - Django builds the JOIN directly against
the underlying table. So a soft-deleted task can still make its parent
Project match a query, even though the task is "deleted".
"""
from decimal import Decimal

from django.db.models import Q
from django.test import TestCase

from workspace.models import Organization, Project, Task


class SoftDeleteLeakTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.project = Project.objects.create(
            organization=cls.org, code="ACM1", name="Atlas", budget_hours=Decimal("10")
        )
        cls.task = Task.objects.create(project=cls.project, title="Delete me")
        cls.task.delete()  # soft delete - sets deleted_at, doesn't remove the row

    def test_soft_deleted_task_hidden_from_default_manager(self):
        self.assertNotIn(self.task, Task.objects.all())

    def test_soft_deleted_task_visible_via_all_objects(self):
        self.assertIn(self.task, Task.all_objects.all())

    def test_soft_deleted_task_hidden_from_reverse_accessor(self):
        self.assertNotIn(self.task, self.project.tasks.all())

    def test_soft_deleted_task_does_not_leak_through_join(self):
        """
        THE LEAK: filtering Project through a `tasks__...` lookup crosses
        into Task's table directly via SQL JOIN, bypassing TaskManager
        entirely. A naive `tasks__id=...` filter incorrectly matches a
        project whose only task is soft-deleted.

        THE FIX: any JOIN traversal into Task must explicitly add
        `tasks__deleted_at__isnull=True` alongside the real condition -
        TaskManager's alive-only scoping does NOT apply across JOINs.
        """
        naive = Project.objects.filter(tasks__id=self.task.id)
        self.assertIn(self.project, naive, "sanity check: JOIN sees deleted rows by default")

        fixed = Project.objects.filter(
            Q(tasks__id=self.task.id) & Q(tasks__deleted_at__isnull=True)
        )
        self.assertNotIn(self.project, fixed)

    def test_alive_task_still_matches_fixed_join(self):
        """The fix shouldn't hide legitimate, non-deleted matches."""
        alive_task = Task.objects.create(project=self.project, title="Still here")
        fixed = Project.objects.filter(
            Q(tasks__id=alive_task.id) & Q(tasks__deleted_at__isnull=True)
        )
        self.assertIn(self.project, fixed)