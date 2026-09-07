"""
Do tarah ke enums:
1. models.TextChoices / IntegerChoices  -> DB column ke liye (Django-aware)
2. plain enum.StrEnum                   -> pure-Python logic ke liye
"""
from enum import StrEnum, auto

from django.db import models


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    MANAGER = "manager", "Manager"
    MEMBER = "member", "Member"

    @property
    def can_manage(self) -> bool:
        return self in {Role.OWNER, Role.MANAGER}


class TaskStatus(models.TextChoices):
    BACKLOG = "backlog", "Backlog"
    IN_PROGRESS = "in_progress", "In progress"
    BLOCKED = "blocked", "Blocked"
    DONE = "done", "Done"

    @classmethod
    def open_statuses(cls) -> list[str]:
        return [cls.BACKLOG, cls.IN_PROGRESS, cls.BLOCKED]


class Priority(models.IntegerChoices):
    LOW = 1, "Low"
    MEDIUM = 2, "Medium"
    HIGH = 3, "High"
    CRITICAL = 4, "Critical"


class Health(StrEnum):
    """Pure Python enum - DB me store nahi hota, compute hota hai."""

    HEALTHY = auto()
    AT_RISK = auto()
    OVER_BUDGET = auto()
