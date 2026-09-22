"""
Race condition demo - 4.2

Do threads same Task ko simultaneously move karne ki koshish karte hain.
Ek artificial delay (SLEEP_SECONDS) read aur write ke beech daala gaya hai
taaki dono threads ka overlap guaranteed ho - warna real hardware itna
fast hota hai ki race kabhi dikhti hi nahi demo me.

Run: python scripts/race_demo.py

NOTE (guide ka disclaimer): SQLite pe locking behaviour Postgres se alag
hai. SQLite ek writer ko poora DB file lock karne deta hai jab tak
transaction commit na ho - is wajah se WITHOUT select_for_update wala
scenario bhi SQLite pe kabhi kabhi "database is locked" error de sakta
hai, jo Postgres pe nahi hoga (Postgres row-level lock deta hai, DB-wide
nahi). Dono versions isliye try/except OperationalError se guarded hain.
"""
import os
import sys
import threading
import time

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import OperationalError, transaction
from django.utils import timezone

from core.enums import TaskStatus
from core.exceptions import InvalidTransition
from workspace.models import ActivityLog, Organization, Project, Task
from workspace.services import ALLOWED_TRANSITIONS, record_activity

SLEEP_SECONDS = 0.5


def unsafe_move(task_id: int, to_status: str, label: str):
    """move_task ka copy, MINUS select_for_update() - the bug."""
    with transaction.atomic():
        task = Task.objects.get(pk=task_id)  # <-- no lock
        print(f"[{label}] read status = {task.status}")

        time.sleep(SLEEP_SECONDS)  # artificial gap - forces overlap

        if to_status not in ALLOWED_TRANSITIONS[task.status]:
            print(f"[{label}] BLOCKED (stale check): {task.status} -> {to_status} not allowed")
            return

        previous, task.status = task.status, to_status
        task.completed_at = timezone.now() if to_status == TaskStatus.DONE else None
        task.save(update_fields=["status", "completed_at", "updated_at"])
        record_activity(None, "task.moved", task, **{"from": previous, "to": to_status})
        print(f"[{label}] wrote status = {to_status} (thought previous was {previous})")


def safe_move(task_id: int, to_status: str, label: str):
    """Real move_task logic - WITH select_for_update()."""
    with transaction.atomic():
        task = Task.objects.select_for_update().get(pk=task_id)
        print(f"[{label}] LOCKED, read status = {task.status}")

        time.sleep(SLEEP_SECONDS)

        if to_status not in ALLOWED_TRANSITIONS[task.status]:
            print(f"[{label}] BLOCKED correctly: {task.status} -> {to_status} not allowed")
            return

        previous, task.status = task.status, to_status
        task.completed_at = timezone.now() if to_status == TaskStatus.DONE else None
        task.save(update_fields=["status", "completed_at", "updated_at"])
        record_activity(None, "task.moved", task, **{"from": previous, "to": to_status})
        print(f"[{label}] wrote status = {to_status} (previous was {previous})")


def run_demo(move_fn, label: str):
    org, _ = Organization.objects.get_or_create(name="RaceDemo", slug="race-demo")
    project, _ = Project.objects.get_or_create(
        organization=org, code="RACE1", name="Race", defaults={"budget_hours": 10}
    )
    task = Task.objects.create(project=project, title="Racey task", status=TaskStatus.IN_PROGRESS)

    print(f"\n=== {label} === task {task.id} starts as {task.status}")

    t1 = threading.Thread(target=move_fn, args=(task.id, TaskStatus.DONE, "Thread-A(DONE)"))
    t2 = threading.Thread(target=move_fn, args=(task.id, TaskStatus.BACKLOG, "Thread-B(BACKLOG)"))

    t1.start()
    time.sleep(0.05)  # tiny stagger so both threads' reads land inside the overlap window
    t2.start()
    t1.join()
    t2.join()

    task.refresh_from_db()
    activity_count = ActivityLog.objects.filter(object_id=task.id, verb="task.moved").count()
    print(f"FINAL status: {task.status}")
    print(f"ActivityLog entries for this task: {activity_count}")


if __name__ == "__main__":
    try:
        run_demo(unsafe_move, "WITHOUT select_for_update")
    except OperationalError as e:
        print("OperationalError (SQLite locking):", e)

    try:
        run_demo(safe_move, "WITH select_for_update")
    except OperationalError as e:
        print("OperationalError (SQLite locking):", e)