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
from workspace.selectors import (burndown, idle_members, org_summary,
                                 project_health, project_list,
                                 top_contributors, workload_forecast)

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

    def test_top_contributors_dense_rank_no_gap_on_tie(self):
        """
        3.2 - Rank() -> DenseRank(). With a tie, Rank() would produce
        1, 1, 3 (skips 2). DenseRank() produces 1, 1, 2 (no gap).

        Build a fresh project so totals are exact and easy to reason about:
        Alice = 100m, Bob = 100m (tie for 1st), Carol = 50m (2nd, not 3rd).
        """
        project2 = Project.objects.create(
            organization=self.org, code="ACM3", name="Tie Test", budget_hours=Decimal("10")
        )
        task = Task.objects.create(project=project2, title="Shared task")
        carol = User.objects.create_user("c@x.com", "pw", full_name="Carol")

        now = timezone.now()
        TimeEntry.objects.create(task=task, user=self.alice, started_at=now, minutes=100)
        TimeEntry.objects.create(task=task, user=self.bob, started_at=now, minutes=100)
        TimeEntry.objects.create(task=task, user=carol, started_at=now, minutes=50)

        rows = top_contributors(project2.pk)

        ranks_by_name = {r["full_name"]: r["rank"] for r in rows}
        self.assertEqual(ranks_by_name["Alice"], 1)
        self.assertEqual(ranks_by_name["Bob"], 1)
        self.assertEqual(ranks_by_name["Carol"], 2)   # NOT 3 - this is what DenseRank guarantees


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


    def test_idle_members_excludes_users_with_recent_entries(self):
        """
        3.3 - idle_members() uses Exists(), not Count()==0.
        Alice has a TimeEntry from `now` (in setUpTestData), so she is
        NOT idle. A second member with no recent entries IS idle.
        """
        carol = User.objects.create_user("c@x.com", "pw", full_name="Carol")
        Membership.objects.create(organization=self.org, user=carol, role="member")

        rows = list(idle_members("acme"))
        idle_user_ids = {m.user_id for m in rows}

        self.assertNotIn(self.alice.id, idle_user_ids)
        self.assertIn(carol.id, idle_user_ids)

    def test_idle_members_excludes_member_with_old_entry_only(self):
        """A member whose only time entry is >7 days old still counts as idle."""
        dave = User.objects.create_user("d@x.com", "pw", full_name="Dave")
        Membership.objects.create(organization=self.org, user=dave, role="member")
        TimeEntry.objects.create(
            task=self.project.tasks.first(), user=dave,
            started_at=timezone.now() - timedelta(days=10), minutes=30,
        )

        idle_user_ids = {m.user_id for m in idle_members("acme")}
        self.assertIn(dave.id, idle_user_ids)

    def test_idle_members_is_single_query(self):
        with self.assertNumQueries(1):
            list(idle_members("acme"))
            

    def test_workload_forecast_buckets_correctly(self):
        today = timezone.localdate()

        light_user = User.objects.create_user("light@x.com", "pw", full_name="Light")
        heavy_user = User.objects.create_user("heavy@x.com", "pw", full_name="Heavy")

        Task.objects.create(
            project=self.project, title="Light task", status=TaskStatus.IN_PROGRESS,
            assignee=light_user, estimate_hours=Decimal("5"),
            due_date=today + timedelta(days=3),
        )
        Task.objects.create(
            project=self.project, title="Heavy task 1", status=TaskStatus.IN_PROGRESS,
            assignee=heavy_user, estimate_hours=Decimal("30"),
            due_date=today + timedelta(days=5),
        )
        Task.objects.create(
            project=self.project, title="Heavy task 2", status=TaskStatus.IN_PROGRESS,
            assignee=heavy_user, estimate_hours=Decimal("30"),
            due_date=today + timedelta(days=10),
        )
        Task.objects.create(
            project=self.project, title="Too far out", status=TaskStatus.IN_PROGRESS,
            assignee=light_user, estimate_hours=Decimal("100"),
            due_date=today + timedelta(days=30),
        )

        rows = {r["full_name"]: r for r in workload_forecast("acme")}

        self.assertEqual(rows["Light"]["forecast_hours"], Decimal("5"))
        self.assertEqual(rows["Light"]["bucket"], "underloaded")

        self.assertEqual(rows["Heavy"]["forecast_hours"], Decimal("60"))
        self.assertEqual(rows["Heavy"]["bucket"], "overloaded")

    def test_workload_forecast_is_single_query(self):
        with self.assertNumQueries(1):
            workload_forecast("acme")