"""
Django middleware = Hono middleware jaisa hi, bas callable class hai.
__init__ ek baar chalta hai (boot pe), __call__ har request pe.
"""
from __future__ import annotations
import re
import uuid
import contextvars
from django.db import connection

# contextvar thread AUR async-task dono me safe hai - global variable mat use karna
_current_org_slug: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_org_slug", default=None
)


def get_current_org_slug() -> str | None:
    return _current_org_slug.get()


class CurrentOrganizationMiddleware:
    """
    Multi-tenant scoping. Slug header ya subdomain se aata hai.
    Isse har manager `.for_current_org()` kar sakta hai bina request pass kiye.
    """

    HEADER = "HTTP_X_ORG"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        slug = request.META.get(self.HEADER) or request.GET.get("org")
        token = _current_org_slug.set(slug)
        request.org_slug = slug
        try:
            return self.get_response(request)
        finally:
            _current_org_slug.reset(token)  # leak mat hone do


class QueryCountMiddleware:
    """DEBUG me har response pe X-Query-Count header - N+1 turant dikh jaata hai."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        before = len(connection.queries)
        response = self.get_response(request)
        response["X-Query-Count"] = str(len(connection.queries) - before)
        return response


import re
import uuid

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Only accept sane client-supplied IDs (log injection / huge header protection)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def get_request_id() -> str | None:
    return _request_id.get()


class RequestIDMiddleware:
    """
    Reuse the incoming X-Request-ID (e.g. from a load balancer) if it looks
    safe, else generate one. Exposed on request, in contextvar, and on response.
    """

    HEADER = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(self.HEADER, "")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex

        token = _request_id.set(request_id)
        request.request_id = request_id
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            _request_id.reset(token)  # same rule as org slug: never leak