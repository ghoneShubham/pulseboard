query = xact database SQL that Django is generating.

explain() = smart shortcut or reading every single row manually.

CaptureQueries = Counts exactly how many times your code hits the database when running a loop avoids n+1 query.

#Task1:
- Signal (pre_save) fills completed_at automatically when status=done, but it's just a convenience layer in Python.
- The real guarantee is the CheckConstraint `done_requires_completed_at` in Task.Meta — that's enforced by the DATABASE itself.
- When I disabled the signal and tried creating a done task without completed_at, Django didn't even get a chance to "validate" — SQLite rejected the INSERT directly with IntegrityError.

#Task2:

A plain ManyToManyField can't hold extra data — the moment you need fields like added_by or added_at on a relationship, you have to promote it to an explicit through-model (same pattern as Membership). But you can't just add through= to an existing M2M field with a normal migration — Django's AlterField doesn't support changing to/from M2M types or adding/removing through=. Doing that generates a migration that fails with ValueError: Cannot alter field ... they are not compatible types. The real fix (for a fresh dev project with no real data to preserve) is deleting the earlier migration files that recorded the plain M2M, resetting the database, and regenerating one clean migration from scratch — since then Django never "remembers" a plain M2M existing and just creates the Tag model, TaskTag through-model, and the M2M-with-through all together in a single step. In a real production system with actual data, this same change would instead require a proper multi-step migration (drop old field, create new model, copy old rows across, then add the new field) instead of just wiping the database.