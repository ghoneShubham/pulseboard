from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from workspace.models import (DailyProjectRollup, Membership, Organization,
                              Project, Task, TimeEntry)

User = get_user_model()


class RollupApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="Acme", slug="acme")
        cls.other_org = Organization.objects.create(name="Beta", slug="beta")
        cls.owner = User.objects.create_user("o@x.com", "pw")
        cls.manager = User.objects.create_user("m@x.com", "pw")
        cls.member = User.objects.create_user("u@x.com", "pw")
        cls.outsider = User.objects.create_user("z@x.com", "pw")
        Membership.objects.create(organization=cls.org, user=cls.owner, role="owner")
        Membership.objects.create(organization=cls.org, user=cls.manager, role="manager")
        Membership.objects.create(organization=cls.org, user=cls.member, role="member")
        Membership.objects.create(organization=cls.other_org, user=cls.outsider, role="owner")

        for org, code in [(cls.org, "A1"), (cls.other_org, "B1")]:
            project = Project.objects.create(organization=org, code=code, name=code)
            task = Task.objects.create(project=project, title="T")
            TimeEntry.objects.create(task=task, user=cls.owner,
                                     started_at=timezone.now(), minutes=30)
        cls.url = "/api/orgs/acme/rollup/"

    def setUp(self):
        cache.clear()   # throttle history lives in the cache; isolate tests

    def _post(self, url=None, **body):
        return self.client.post(url or self.url, body, content_type="application/json")

    def test_owner_can_trigger(self):
        self.client.force_login(self.owner)
        res = self._post(days=7)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["rows_upserted"], 1)

    def test_only_own_org_is_rebuilt(self):
        self.client.force_login(self.owner)
        self._post(days=7)
        codes = set(DailyProjectRollup.objects.values_list("project__code", flat=True))
        self.assertEqual(codes, {"A1"})   # B1 untouched

    def test_non_owners_get_403(self):
        for user in (self.manager, self.member, self.outsider):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                res = self._post()
                self.assertEqual(res.status_code, 403)
                self.assertEqual(res.json()["error"]["code"], "permission_denied")

    def test_unknown_org_looks_same_as_forbidden(self):
        self.client.force_login(self.owner)
        res = self._post(url="/api/orgs/nope/rollup/")
        self.assertEqual(res.status_code, 403)

    def test_anonymous_rejected(self):
        self.assertEqual(self._post().status_code, 403)

    def test_days_validated(self):
        self.client.force_login(self.owner)
        self.assertEqual(self._post(days=0).status_code, 400)
        self.assertEqual(self._post(days=91).status_code, 400)

    def test_throttled_after_two_per_hour(self):
        self.client.force_login(self.owner)
        self.assertEqual(self._post().status_code, 200)
        self.assertEqual(self._post().status_code, 200)
        self.assertEqual(self._post().status_code, 429)