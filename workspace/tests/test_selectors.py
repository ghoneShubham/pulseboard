"""
assertNumQueries = Django ka sabse underrated testing tool.
Query count ko test me lock kar do; koi N+1 introduce karega toh CI red.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.enums import TaskStatus
from workspace.models import Membership, Organization, Project, Task, TimeEntry
from workspace.selectors import (burndown, org_summary, project_health,
                                 project_list, top_contributors)

User = get_user_model()


class SelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # setUpTestData class me ek baar chalta hai (transaction rollback per test)
        # setUp ke muqable kaafi tez.
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.alice = User.objects.create_user("a@x.com", "pw", full_name="Alice")
        cls.bob = User.objects.create_user("b@x.com", "pw", full_name="Bob")
        Membership.objects.create(organization=cls.org, user=cls.alice, role="owner")

        cls.project = Project.objects.create(
            organization=cls.org, code="ACM1", name="Atlas", budget_hours=Decimal("10")
        )
        now = timezone.now()
        for i in range(4):
            task = Task.objects.create(
                project=cls.project, title=f"T{i}",
                status=TaskStatus.DONE if i == 0 else TaskStatus.IN_PROGRESS,
                completed_at=now if i == 0 else None,
                assignee=cls.alice if i % 2 == 0 else cls.bob,
                estimate_hours=Decimal("2"),
                due_date=(now - timedelta(days=1)).date() if i == 3 else None,
            )
            # Alice ko zyada minutes - ranking test deterministic rahe
            TimeEntry.objects.create(
                task=task, user=task.assignee,
                started_at=now - timedelta(days=i),
                minutes=60 if task.assignee_id == cls.alice.id else 30,
            )

    def test_project_list_avoids_n_plus_one(self):
        # 1 query: projects + organization JOIN (select_related)
        # 1 query: prefetched open tasks + assignee JOIN
        # Bina inke ye 1 + N + N hota. Number badhe toh test fail = early warning.
        with self.assertNumQueries(2):
            for project in project_list("acme"):
                _ = project.organization.name
                _ = [t.assignee for t in project.open_tasks]

    def test_project_health_is_single_query(self):
        with self.assertNumQueries(1):
            rows = project_health("acme")
        row = rows[0]
        self.assertEqual(row.logged_minutes, 180)
        self.assertEqual(row.open_tasks, 3)
        self.assertEqual(row.logged_hours, Decimal("3.00"))
        self.assertEqual(row.utilisation, Decimal("30.0"))
        self.assertEqual(row.health, "healthy")

    def test_project_health_avg_cycle_time(self):
        """
        3.1 - avg_cycle_time = avg(completed_at - created_at), DONE tasks only.
        Fixture has exactly one DONE task (T0), so avg == that one task's
        own cycle time. Still costs only 1 query (same annotate() call).
        """
        done_task = Task.objects.get(project=self.project, title="T0")
        expected = done_task.completed_at - done_task.created_at

        with self.assertNumQueries(1):
            rows = project_health("acme")
        row = rows[0]

        #self.assertIsNotNone(row.avg_cycle_time)
        self.assertAlmostEqual(
            row.avg_cycle_time.total_seconds(), expected.total_seconds(), delta=1
        )


    def test_top_contributors_densranking(self):
        rows = top_contributors(self.project.pk)

        print("\nTOP CONTRIBUTORS:")
        print("Number of rows:", len(rows))

        for row in rows:
            print(row)

        self.assertEqual(rows[0]["full_name"], "Alice")
        self.assertEqual(rows[0]["total_minutes"], 120)
        self.assertEqual(rows[0]["rank"], 1)

    def test_burndown_fills_missing_days(self):
        points = burndown(self.project.pk, days=14)
        self.assertEqual(len(points), 14)
        self.assertEqual(points[-1].cumulative_minutes, 180)
        self.assertTrue(all(p.cumulative_minutes >= 0 for p in points))

    def test_org_summary_conditional_aggregates(self):
        org_summary.invalidate("acme")
        summary = org_summary("acme")
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["done"], 1)
        self.assertEqual(summary["logged_minutes"], 180)

    def test_soft_delete_hides_rows_but_keeps_them(self):
        Task.objects.filter(title="T1").delete()
        self.assertEqual(Task.objects.count(), 3)
        self.assertEqual(Task.all_objects.count(), 4)

    def test_queryset_methods_chain(self):
        self.assertEqual(Task.objects.for_org("acme").open().overdue().count(), 1)
        t1 = Task.objects.for_org("acme").with_logged_minutes().get(title="T1")
        self.assertEqual(t1.logged_minutes, 30)  # Bob ka task
