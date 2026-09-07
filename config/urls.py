from django.contrib import admin
from django.urls import include, path

from workspace.views import ProjectDetailView, ProjectReportView, project_pulse

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("workspace.api.urls")),
    path("reports/projects/", ProjectReportView.as_view(), name="project-report"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:pk>/pulse/", project_pulse, name="project-pulse"),
    path("api-auth/", include("rest_framework.urls")),
]
