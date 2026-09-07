from __future__ import annotations

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """
    QuerySet subclass = chainable custom methods.
    Manager pe method likhoge toh chain toot jaayegi; QuerySet pe likho
    aur `.as_manager()` se manager bana lo - best of both.
    """

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):  # noqa: A003 - queryset.delete() ko override kar rahe hain
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(deleted_at=None)


class AliveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager - deleted rows kabhi dikhte hi nahi."""

    def get_queryset(self):
        return super().get_queryset().alive()
