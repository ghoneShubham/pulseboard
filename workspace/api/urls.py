from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import OrgRollupView,ProjectViewSet, TaskViewSet, TimeEntryViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("tasks", TaskViewSet, basename="task")
router.register("time-entries", TimeEntryViewSet, basename="timeentry")

urlpatterns = router.urls + [
    path("orgs/<slug:slug>/rollup/", OrgRollupView.as_view(), name="org-rollup"),
]
