"""
Django middleware = Hono middleware jaisa hi, bas callable class hai.
__init__ ek baar chalta hai (boot pe), __call__ har request pe.
"""
from __future__ import annotations

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
