#task4.1:
-Built reassign_task()
-added a new check (Membership.objects.filter(user=to_user, organization=...).exists()) to enforce the assignee must belong to the same org, logged the change via record_activity(), and invalidated the org_summary cache.
-made test 
#task4.2:
-race conditions-two threads -calling a stripped-down move_task on the SAME task
(IN_PROGRESS), one trying to move to DONE, one trying BACKLOG, with an
artificial 0.5s sleep between read and write to force overlap.
- select_for_update()-without it it does not give error 
-with it it gives error 

#task4.3:
-log_time used innitialy sum() 
-uses Project.logged_minutes (an F()-updated counter)
instead of a live Sum() over TimeEntry every call 
-benifit: no need to do the cal every time 

#task4.4:
with on_commit : after rollback no log  saved 
without on_commit: records  that never happned after using the rollback .
