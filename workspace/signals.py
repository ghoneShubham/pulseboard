"""
Signals: decoupling ka tool, business logic ka nahi.

Use karo -> cross-app reactions (cache bust, search index, thumbnail)
Mat karo -> core rules (invisible control flow, testing dukhdayi, bulk ops skip)

Yahan ek "safe" use dikhaya hai: derived counter/cache invalidation.
"""
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from core.enums import TaskStatus

from .models import Task, TimeEntry


@receiver(pre_save, sender=Task, dispatch_uid="task_stamp_completed_at")
def stamp_completed_at(sender, instance: Task, **kwargs):
    """Safety net - koi service bypass karke save kare toh bhi invariant bacha rahe."""
    if instance.status == TaskStatus.DONE and instance.completed_at is None:
        from django.utils import timezone
        instance.completed_at = timezone.now()
    elif instance.status != TaskStatus.DONE:
        instance.completed_at = None


@receiver([post_save, post_delete], sender=TimeEntry, dispatch_uid="entry_bust_cache")
def bust_rollup_cache(sender, instance: TimeEntry, **kwargs):
    from django.core.cache import cache

    cache.delete(f"rollup:{instance.task.project_id}")
    # WARNING: ye bulk_create/queryset.update pe FIRE NAHI hota.
    # Isliye nightly rollup command hi source of truth hai.
