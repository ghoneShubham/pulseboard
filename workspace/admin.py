from django.contrib import admin, messages
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html

from .models import (ActivityLog, ArchivedProject, DailyProjectRollup,
                     Membership, Organization, Project, Task, TimeEntry)
from .services import bump_priority


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ["title", "status", "priority", "assignee", "due_date"]
    show_change_link = True


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "member_count", "project_count"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MembershipInline]
    search_fields = ["name", "slug"]

    def get_queryset(self, request):
        # Admin list page bhi N+1 se marta hai - yahin annotate kar do
        return super().get_queryset(request).annotate(
            _members=Count("memberships", distinct=True),
            _projects=Count("projects", distinct=True),
        )

    @admin.display(description="Members", ordering="_members")
    def member_count(self, obj):
        return obj._members

    @admin.display(description="Projects", ordering="_projects")
    def project_count(self, obj):
        return obj._projects


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "organization", "budget_hours", "logged_hours", "is_archived"]
    list_filter = ["is_archived", "organization"]
    search_fields = ["code", "name"]
    list_select_related = ["organization"]
    inlines = [TaskInline]
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_minutes=Sum("tasks__time_entries__minutes"))

    @admin.display(description="Logged (h)", ordering="_minutes")
    def logged_hours(self, obj):
        return round((obj._minutes or 0) / 60, 1)


@admin.register(ArchivedProject)
class ArchivedProjectAdmin(admin.ModelAdmin):
    """Proxy model ka faayda - alag admin screen, zero extra tables."""

    list_display = ["code", "name", "organization"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_archived=True)


@admin.action(description="Bump priority by 1")
def action_bump_priority(modeladmin, request, queryset):
    changed = bump_priority(task_ids=list(queryset.values_list("pk", flat=True)))
    modeladmin.message_user(request, f"{changed} task(s) bumped.", messages.SUCCESS)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project_link", "status", "priority", "assignee", "due_date"]
    list_filter = ["status", "priority", "project__organization"]
    search_fields = ["title", "description"]
    list_select_related = ["project", "assignee"]
    autocomplete_fields = ["project", "assignee"]
    date_hierarchy = "created_at"
    actions = [action_bump_priority]

    @admin.display(description="Project")
    def project_link(self, obj):
        url = reverse("admin:workspace_project_change", args=[obj.project_id])
        return format_html('<a href="{}">{}</a>', url, obj.project.code)


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ["task", "user", "started_at", "minutes"]
    list_select_related = ["task", "user"]
    date_hierarchy = "started_at"


admin.site.register([ActivityLog, DailyProjectRollup])
