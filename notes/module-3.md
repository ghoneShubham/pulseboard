#Task 3.3:
-func for members not logged in for about 7 days 
-used exist() it uses composite index so doesnot scan every row or record and returs the result 
-count()==0 it scans for entire row or record so it is time consuming 
#task 3.4:
-prefetch_related: uses seprates queies and python 
-selected_related : uses 1 quere and join 
#task3.5:
-Ek workload_forecast(org_slug) selector banaya jo har user ke liye next 14 days ke open tasks ka estimate sum kare,
-aur unhe Case/When se underloaded / balanced / overloaded bucket me daale.
#task3.6:
-Tested removing partition_by=[F("user_id")] from the window function. When the query is already filtered to one user_id (as the real function does), output was identical — nothing to partition since only one user's rows exist.
#task3.7:
-added seed demo data
-Measured (5-run average, same project) burndown(), burndown_from_rollup(),org_summary() 
-live and rollup versions produce IDENTICAL(day, minutes, cumulative_minutes) tuples

