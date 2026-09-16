query = xact database SQL that Django is generating.

explain() = smart shortcut or reading every single row manually.

CaptureQueries = Counts exactly how many times your code hits the database when running a loop avoids n+1 query.

#Task 1:
-we create a signal.py it sends signals when the condition in signal.py matches 
-in that signal.py we created logic for signal if a task is saved it will give signal with completed at 
-if we save a task using shell it prints the completed at 
-if we comment the signals.py  it will show integrity error.

#Task 1.2:
-many to many field: cannot hold extra field like a tag .eg added_by
-for that we use a through model,once plane m2m created you cannot  alter it 
-soln: delete migration add again a fresh migrations 
-we created a task table and  tag table in workspace models  a join table will be hidden in the migra
-convertingto through : new model throughtag- add new colm need + .foreginkey task and tag   
-and just add this in task table ka  tag at end  through="TaskTag"

task 1.3
-TimeEntry.started_at currently accepts any datetime-even from future
-makes no sense (you can't log time for work you haven't done yet).
-we added a custom check constraints in time entry model using now .
-in python shell check if it is working properly 

Task 1.4
-compositeindex : left to right pattern 
-created a query for searching project-status-duedate 
-according to index created 
-automatic index
-status,duedate find  karna tha lekin bech se nahi find kar sakte 
-automatic index create karta hai kuki humne index=True kiya tha 
-due_date nahi karta badme filter karta hai staus =?

Task 1.5
-abstract : no table creation for parent , only child tables created 
-multi-table: tables created for parent and child 
-in this #Proxi:
-tables not created only the existing bheaviour changes 
-created a new critical task model which is proxy 
-and created the critical task manager for queryset
-on the python shell we see  count changes 


