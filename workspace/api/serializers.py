"""
Serializer = validation + shape. Zod/valibot ka Django equivalent.
Rule: validate_* me shape/field rules; cross-object business rules service me.
"""
from rest_framework import serializers

from core.enums import TaskStatus

from ..models import Project, Task, TimeEntry


class ProjectSerializer(serializers.ModelSerializer):
    organization = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    logged_hours = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "code", "name", "organization", "budget_hours", "is_archived", "logged_hours"]

    def get_logged_hours(self, obj) -> float:
        # annotate se aata hai - agar view ne annotate nahi kiya toh 0
        return round(getattr(obj, "logged_minutes", 0) / 60, 2)


class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source="assignee.full_name", read_only=True, default="")
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "project", "title", "description", "status", "priority",
            "assignee", "assignee_name", "estimate_hours", "due_date", "is_open",
        ]
        read_only_fields = ["status"]  # status sirf /move endpoint se badlega

    def validate_estimate_hours(self, value):
        if value > 200:
            raise serializers.ValidationError("Estimate 200h se zyada? Task tod do.")
        return value

    def validate(self, attrs):
        if attrs.get("priority") == 4 and not attrs.get("due_date"):
            raise serializers.ValidationError({"due_date": "Critical task ko due date chahiye."})
        return attrs


class MoveTaskSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=TaskStatus.choices)


class LogTimeSerializer(serializers.Serializer):
    started_at = serializers.DateTimeField()
    minutes = serializers.IntegerField(min_value=1, max_value=1440)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = ["id", "task", "user", "started_at", "minutes", "note"]
        read_only_fields = ["user"]
