from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet, TaskViewSet, TimeEntryViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("tasks", TaskViewSet, basename="task")
router.register("time-entries", TimeEntryViewSet, basename="timeentry")

urlpatterns = router.urls
