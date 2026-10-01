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
#task5.4:
-custom middlerware for middleware + log filter
The plan is three pieces: a ContextVar that holds the ID, a middleware that sets and resets it per request, and a logging.Filter that stamps the ID onto every log record.

#task5.6:
-Trigger daily_rollup via API
Extract the rebuild logic into services.rebuild_rollups().
Add services.trigger_rollup() for the owner check and audit log.
Add a thin APIView with throttle_scope = "rollup".
