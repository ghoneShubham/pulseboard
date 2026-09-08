from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.enums import TaskStatus
from workspace.models import Membership, Organization, Project, Task

User = get_user_model()


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.owner = User.objects.create_user("o@x.com", "pw", full_name="Owner")
        cls.outsider = User.objects.create_user("z@x.com", "pw", full_name="Zed")
        Membership.objects.create(organization=cls.org, user=cls.owner, role="owner")
        cls.project = Project.objects.create(
            organization=cls.org, code="ACM1", name="Atlas", budget_hours=Decimal("50")
        )
        cls.task = Task.objects.create(project=cls.project, title="T", status=TaskStatus.IN_PROGRESS)

    def test_requires_auth(self):
        self.assertEqual(self.client.get("/api/projects/").status_code, 403)

    def test_tenant_scoping(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get("/api/projects/").json()["count"], 0)

    def test_project_list_has_annotated_hours(self):
        self.client.force_login(self.owner)
        res = self.client.get("/api/projects/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["results"][0]["logged_hours"], 0)

    def test_domain_error_becomes_clean_json(self):
        self.client.force_login(self.owner)
        res = self.client.post(
            f"/api/tasks/{self.task.pk}/move/", {"to_status": "backlog"}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        res = self.client.post(
            f"/api/tasks/{self.task.pk}/move/", {"to_status": "done"}, content_type="application/json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"]["code"], "invalid_transition")

    def test_log_time_endpoint(self):
        self.client.force_login(self.owner)
        res = self.client.post(
            f"/api/tasks/{self.task.pk}/log-time/",
            {"started_at": timezone.now().isoformat(), "minutes": 45},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["minutes"], 45)

    def test_query_count_header_present(self):
        self.client.force_login(self.owner)
        res = self.client.get("/api/projects/")
        self.assertIn("X-Query-Count", res)
        
   
