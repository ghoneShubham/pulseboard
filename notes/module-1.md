query = xact database SQL that Django is generating.

explain() = smart shortcut or reading every single row manually.

CaptureQueries = Counts exactly how many times your code hits the database when running a loop avoids n+1 query.

#Task1:
- Signal (pre_save) fills completed_at automatically when status=done, but it's just a convenience layer in Python.
- The real guarantee is the CheckConstraint `done_requires_completed_at` in Task.Meta — that's enforced by the DATABASE itself.
- When I disabled the signal and tried creating a done task without completed_at, Django didn't even get a chance to "validate" — SQLite rejected the INSERT directly with IntegrityError.
