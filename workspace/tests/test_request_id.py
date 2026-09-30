import logging
import re

from django.test import RequestFactory, TestCase

from core.log_filters import RequestIDFilter
from core.middleware import RequestIDMiddleware, get_request_id


class RequestIDTests(TestCase):
    def _run(self, **headers):
        seen = {}

        def view(request):
            seen["ctx"] = get_request_id()
            seen["req"] = request.request_id
            from django.http import HttpResponse
            return HttpResponse("ok")

        response = RequestIDMiddleware(view)(RequestFactory().get("/", **headers))
        return response, seen

    def test_generates_id_when_missing(self):
        response, seen = self._run()
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")
        self.assertEqual(seen["ctx"], response["X-Request-ID"])
        self.assertEqual(seen["req"], seen["ctx"])

    def test_honours_safe_incoming_id(self):
        response, _ = self._run(HTTP_X_REQUEST_ID="abc-123")
        self.assertEqual(response["X-Request-ID"], "abc-123")

    def test_rejects_unsafe_incoming_id(self):
        response, _ = self._run(HTTP_X_REQUEST_ID="bad id\nINJECT")
        self.assertNotIn("INJECT", response["X-Request-ID"])

    def test_contextvar_reset_after_request(self):
        self._run()
        self.assertIsNone(get_request_id())

    def test_filter_stamps_record(self):
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
        RequestIDFilter().filter(record)
        self.assertEqual(record.request_id, "-")   # outside a request

    def test_filter_uses_current_id_inside_request(self):
        captured = {}

        def view(request):
            record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
            RequestIDFilter().filter(record)
            captured["id"] = record.request_id
            from django.http import HttpResponse
            return HttpResponse()

        response = RequestIDMiddleware(view)(RequestFactory().get("/"))
        self.assertEqual(captured["id"], response["X-Request-ID"])