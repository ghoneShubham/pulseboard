from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from core.enums import Priority, Role, TaskStatus
from core.models import SoftDeleteModel, TimeStampedModel

from .managers import TaskManager


class Organization(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Membership(TimeStampedModel):
    """Through-model. M2M pe extra fields chahiye toh `through=` lagana padta hai."""

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="uniq_org_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


class Project(TimeStampedModel, SoftDeleteModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="projects")
    code = models.CharField(max_length=12)
    name = models.CharField(max_length=160)
    budget_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    is_archived = models.BooleanField(default=False)
    activity = GenericRelation("workspace.ActivityLog")

    class Meta:
        ordering = ["code"]
        constraints = [
            # DB-level constraint. Sirf clean()/validators pe mat bharosa karo -
            # bulk_create aur raw SQL unhe bypass kar dete hain.
            models.UniqueConstraint(fields=["organization", "code"], name="uniq_org_project_code"),
            models.CheckConstraint(condition=models.Q(budget_hours__gte=0), name="budget_non_negative"),
        ]
        indexes = [models.Index(fields=["organization", "is_archived"], name="proj_org_arch_idx")]

    def __str__(self) -> str:
        return f"[{self.code}] {self.name}"

    def audit_label(self) -> str:
        return f"Project<{self.code}>"


class Tag(TimeStampedModel):
    name = models.CharField(max_length=40, unique=True)

    def __str__(self) -> str:
        return self.name
class Task(TimeStampedModel, SoftDeleteModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.BACKLOG, db_index=True)
    priority = models.IntegerField(choices=Priority.choices, default=Priority.MEDIUM)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="tasks",
    )
    estimate_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    activity = GenericRelation("workspace.ActivityLog")
    tags = models.ManyToManyField(Tag, related_name="tasks", blank=True, through="TaskTag")

    objects = TaskManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-priority", "due_date"]
        indexes = [
            # Composite index - column order matter karta hai (leftmost prefix rule)
            models.Index(fields=["project", "status", "due_date"], name="task_proj_status_idx"),
            models.Index(fields=["assignee", "status"], name="task_assignee_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(estimate_hours__gte=0), name="estimate_non_negative"),
            # done hai toh completed_at hona chahiye - invariant DB me lock
            models.CheckConstraint(
                condition=~models.Q(status="done") | models.Q(completed_at__isnull=False),
                name="done_requires_completed_at",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def audit_label(self) -> str:
        return f"Task<{self.pk}:{self.title[:24]}>"

    @property
    def is_open(self) -> bool:
        return self.status in TaskStatus.open_statuses()
    
class TaskTag(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "tag"], name="uniq_task_tag"),
        ]


class TimeEntry(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_entries")
    started_at = models.DateTimeField(db_index=True)
    minutes = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name_plural = "time entries"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(minutes__gt=0) & models.Q(minutes__lte=1440),
                name="minutes_within_day",
            ),
        ]
        indexes = [models.Index(fields=["user", "started_at"], name="entry_user_date_idx")]

    def __str__(self) -> str:
        return f"{self.minutes}m on {self.task_id}"


class ActivityLog(TimeStampedModel):
    """
    Generic FK (contenttypes) - ek hi audit table kisi bhi model se attach.
    Trade-off: DB-level FK integrity nahi milti aur JOIN mehnga hota hai.
    Isiliye read-heavy path pe iska use mat karo.
    """

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    verb = models.CharField(max_length=40)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"], name="activity_target_idx")]

    def __str__(self) -> str:
        return f"{self.actor} {self.verb} {self.target}"


class DailyProjectRollup(models.Model):
    """
    Pre-aggregated reporting table. Live aggregation slow hone lage toh
    nightly job isme likhta hai aur dashboard yahin se padhta hai.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="rollups")
    day = models.DateField()
    minutes = models.PositiveIntegerField(default=0)
    entries = models.PositiveIntegerField(default=0)
    contributors = models.PositiveIntegerField(default=0)
    refreshed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-day"]
        constraints = [
            models.UniqueConstraint(fields=["project", "day"], name="uniq_project_day"),
        ]

    def __str__(self) -> str:
        return f"{self.project_id} {self.day}: {self.minutes}m"


class ArchivedProject(Project):
    """
    Proxy model - naya table nahi banta. Same data, alag default queryset,
    alag admin entry. Admin me "sirf archived" view chahiye toh perfect.
    """

    class Meta:
        proxy = True
        verbose_name = "archived project"
