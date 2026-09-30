#Task5.1:
TimeEntryViewSet:
-Built IsOwnEntryOrManager(IsOrgMember):created this for role based access control
-member:list and delete its own  timeentry 
-manager:list and delete all timeentrys
-in views created a api using python func containing timeentryviewset.
#task5.2:
-has_permision returned true 
-Anonymous (no login): normally 403.-Authenticated outsider:no leake either way .
- has_permission's actual job is failing FAST and CLEAN
before the query layer runs, so breaking it doesn't leak data here, but
does turn a handled 403 into an unhandled 500 - a robustness bug, not
a security leak, in this specific case.
#task5.3:
-Built project_report_async() using the same asyncio.gather + sync_to_async
pattern as project_pulse - runs project_health() and org_summary()
"concurrently."
- SYNC:  ~5.2ms
- ASYNC: ~4.6ms