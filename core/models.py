"""
Abstract base models. `abstract = True` matlab iska koi table nahi banta -
columns child model me copy ho jaate hain. Ye Django ka DRY ka core hai.

Teen tarah ki inheritance yaad rakho:
  abstract        -> no table, columns inherit (99% cases)
  multi-table     -> parent ka apna table + implicit OneToOne (JOIN cost)
  proxy           -> same table, alag behaviour/manager/ordering
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from core.managers import AliveManager, SoftDeleteQuerySet


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = AliveManager()
    all_objects = SoftDeleteQuerySet.as_manager()  # admin/audit ke liye

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def hard_delete(self):
        super().delete()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
