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

