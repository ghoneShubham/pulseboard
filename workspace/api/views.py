from django.db.models import IntegerField, Subquery
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Project, Task
from ..selectors import _logged_minutes_sq, burndown, org_summary, top_contributors
from ..services import log_time, move_task
from .permissions import IsOrgMember
from .serializers import (LogTimeSerializer, MoveTaskSerializer,
                          ProjectSerializer, TaskSerializer, TimeEntrySerializer)


class ProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsOrgMember]
    throttle_scope = "reports"

    def get_queryset(self):
        # Tenant scoping queryset me - view me kabhi bhoolna nahi chahiye
        return (
            Project.objects.filter(organization__memberships__user=self.request.user)
            .select_related("organization")
            .annotate(logged_minutes=Coalesce(Subquery(_logged_minutes_sq(), output_field=IntegerField()), 0))
            .distinct()
        )

    @action(detail=True, methods=["get"])
    def contributors(self, request, pk=None):
        self.get_object()  # permission check chalta hai
        return Response(top_contributors(int(pk)))

    @action(detail=True, methods=["get"])
    def burndown(self, request, pk=None):
        self.get_object()
        days = int(request.query_params.get("days", 14))
        return Response([
            {"day": p.day, "minutes": p.minutes, "cumulative": p.cumulative_minutes}
            for p in burndown(int(pk), days=days)
        ])

    @action(detail=False, methods=["get"])
    def summary(self, request):
        slug = request.query_params.get("org") or getattr(request, "org_slug", "")
        return Response(org_summary(slug))


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [IsOrgMember]

    def get_queryset(self):
        qs = (
            Task.objects.filter(project__organization__memberships__user=self.request.user)
            .select_related("project", "assignee")
            .distinct()
        )
        params = self.request.query_params
        if term := params.get("q"):
            qs = qs.search(term)
        if params.get("open") == "1":
            qs = qs.open()
        if params.get("overdue") == "1":
            qs = qs.overdue()
        return qs

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        self.get_object()
        payload = MoveTaskSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        # DomainError uthega toh core.exceptions.domain_exception_handler
        # use clean JSON error me convert kar dega
        task = move_task(task_id=int(pk), to_status=payload.validated_data["to_status"], actor=request.user)
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="log-time")
    def log_time_action(self, request, pk=None):
        self.get_object()
        payload = LogTimeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        entry = log_time(task_id=int(pk), user=request.user, **payload.validated_data)
        return Response(TimeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
