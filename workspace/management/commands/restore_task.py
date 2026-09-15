"""
Restore a soft-deleted Task by id.
    python manage.py restore_task <id>

Task.objects (TaskManager) sirf alive tasks dikhata hai, isliye ek deleted
task ko *find* karne ke liye Task.all_objects use karna zaroori hai.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from workspace.models import Task


class Command(BaseCommand):
    help = "Restore a soft-deleted task by its id."

    def add_arguments(self, parser):
        parser.add_argument("task_id", type=int)

    def handle(self, *args, **opts):
        task_id = opts["task_id"]

        try:
            task = Task.all_objects.get(pk=task_id)
        except Task.DoesNotExist:
            raise CommandError(f"No task found with id={task_id}")

        if task.deleted_at is None:
            self.stdout.write(self.style.WARNING(f"Task {task_id} ('{task.title}') is not deleted - nothing to do."))
            return

        Task.all_objects.filter(pk=task_id).restore()

        self.stdout.write(self.style.SUCCESS(f"Restored task {task_id} ('{task.title}')."))