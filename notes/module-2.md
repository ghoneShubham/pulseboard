#Task 2.1:
-stale():finds tasks that are still open but haven't been touched in a while task might be forgotten, stuck .
-helps to find which task are gone quite 
-in workspace/managers.py we add a functin for stale 
-to test  we create a new test file for managers 
-test works finds  not done task, open task updated older than 7 days 

#task 2.2:
-built custom this_week(), by_user(user), longer_than(minutes) on cust TimeEntryQuerySet
- created a TimeEntryManager model 
-this_week() uses timezone.localdate() and weekday() to find Monday of the
current week, then filters started_at__date__gte that Monday - so it's
timezone-aware and resets every Monday, not just "last 7 days" like
Task.stale().

#task 2.3:
-written a test for soft delete where 1 failed due to the orm does not look the managers 
-due to the join if we filter for a deleted task with its  id it will show 
-fix is that we manualy add tasks__deleted_at__isnull=True with the join 

#task2.4
-soft delete doesn't remove a row — it just stamps deleted_at with a timestamp, and the normal Task.objects manager auto-hides anything with that stamp
-manager hides anything with None
-restore cleans the flag 