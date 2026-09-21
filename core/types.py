"""
Typed boundaries. Service layer dict nahi, ye objects return karta hai -
IDE autocomplete + refactor safety milti hai (TS jaisa feel).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol, TypedDict



@dataclass(frozen=True, slots=True)
class ProjectHealth:
    project_id: int
    code: str
    name: str
    budget_hours: Decimal
    logged_minutes: int
    open_tasks: int
    health: str
    has_overdue: bool = False
    avg_cycle_time: timedelta | None = None

    @property
    def logged_hours(self) -> Decimal:
        return (Decimal(self.logged_minutes) / 60).quantize(Decimal("0.01"))

    @property
    def utilisation(self) -> Decimal:
        if not self.budget_hours:
            return Decimal("0")
        return (self.logged_hours / self.budget_hours * 100).quantize(Decimal("0.1"))


@dataclass(slots=True)
class BurndownPoint:
    day: date
    minutes: int
    cumulative_minutes: int = 0


class ContributorRow(TypedDict):
    user_id: int
    full_name: str
    total_minutes: int
    rank: int
    
class WorkloadRow(TypedDict):
    user_id: int
    full_name: str
    forecast_hours: Decimal
    bucket: str


class SupportsAudit(Protocol):
    """Structural typing - inheritance ki zaroorat nahi, bas shape match ho."""

    pk: int

    def audit_label(self) -> str: ...


@dataclass
class SeedPlan:
    orgs: int = 1
    projects_per_org: int = 3
    tasks_per_project: int = 25
    entries_per_task: int = 4
    tags: list[str] = field(default_factory=lambda: ["api", "ui", "infra"])
