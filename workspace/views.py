"""
Class-based views + mixins. CBV ka asli faayda: reusable behaviour
(LoginRequiredMixin, pagination, form handling) inherit ho jaata hai.
"""
from __future__ import annotations

import asyncio

from asgiref.sync import sync_to_async
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import DetailView, ListView

from .models import Project
from .selectors import burndown, org_summary, project_health, top_contributors


class OrgScopedMixin:
    """Har view me tenant filter repeat na karna pade."""

    def get_org_slug(self) -> str:
        return self.request.GET.get("org") or getattr(self.request, "org_slug", "") or ""


class ProjectReportView(LoginRequiredMixin, OrgScopedMixin, ListView):
    template_name = "workspace/project_report.html"
    context_object_name = "rows"
    paginate_by = 25

    def get_queryset(self):
        return project_health(self.get_org_slug())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = org_summary(self.get_org_slug())
        return ctx


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "workspace/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        return Project.objects.select_related("organization")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["contributors"] = top_contributors(self.object.pk)
        ctx["burndown"] = burndown(self.object.pk)
        return ctx


async def project_pulse(request, pk: int):
    """
    Async view. Django 4.1+ me ORM ke async variants hain: aget/acreate/async for.
    Faayda tab hai jab I/O parallel ho - yahan do independent queries
    asyncio.gather se saath me chal rahi hain.
    """
    project = await Project.objects.select_related("organization").aget(pk=pk)

    contributors, points = await asyncio.gather(
        sync_to_async(top_contributors)(project.pk),   # sync fn -> thread pool
        sync_to_async(burndown)(project.pk),
    )

    recent = [t.title async for t in project.tasks.open().order_by("-priority")[:5]]

    return JsonResponse({
        "project": project.code,
        "organization": project.organization.name,
        "top_contributors": contributors,
        "burndown": [{"day": p.day.isoformat(), "minutes": p.minutes} for p in points],
        "hot_tasks": recent,
    })
