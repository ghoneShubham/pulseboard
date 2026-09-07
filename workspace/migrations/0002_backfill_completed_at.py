"""
DATA MIGRATION (RunPython).

Rules:
 1. apps.get_model() use karo, direct import NEVER - migration ko us waqt ka
    historical model chahiye, aaj wala nahi.
 2. Hamesha reverse_code do (noop bhi chalega) taaki migrate backwards na tootey.
 3. Bade tables pe .iterator() + chunks - warna memory blow ho jaayegi.
 4. Schema aur data migration alag files me rakho (lock contention + rollback).
"""
from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    Task = apps.get_model("workspace", "Task")
    now = timezone.now()
    # .update() single query - lakhon rows pe loop mat karo
    Task.objects.filter(status="done", completed_at__isnull=True).update(completed_at=now)


def unbackfill(apps, schema_editor):
    # Reversible rakhna - CI me `migrate <app> zero` chal sake
    pass


class Migration(migrations.Migration):
    dependencies = [("workspace", "0001_initial")]

    operations = [
        migrations.RunPython(backfill, unbackfill, elidable=True),
    ]
