from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet, TaskViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("tasks", TaskViewSet, basename="task")

urlpatterns = router.urls
