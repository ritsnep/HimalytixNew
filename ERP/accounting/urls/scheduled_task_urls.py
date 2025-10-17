"""
URL Configuration for Scheduled Tasks - Phase 3 Task 4

Routes:
- /periods/ → List accounting periods
- /periods/<id>/ → Period details
- /periods/<id>/close/ → Close period
- /recurring-entries/ → List recurring entries
- /recurring-entries/create/ → Create recurring entry
- /recurring-entries/<id>/edit/ → Edit recurring entry
- /recurring-entries/<id>/delete/ → Delete recurring entry
- /recurring-entries/post/ → Post due entries
- /scheduled-reports/ → List scheduled reports
- /scheduled-reports/create/ → Create report
- /scheduled-reports/<id>/edit/ → Edit report
- /scheduled-reports/<id>/delete/ → Delete report
- /task/<task_id>/status/ → Check task status
- /task-history/ → View task execution history
"""

from django.urls import path
from accounting.views.scheduled_task_views import (
    PeriodClosingListView,
    PeriodClosingDetailView,
    PeriodClosingView,
    RecurringEntryListView,
    RecurringEntryCreateView,
    RecurringEntryUpdateView,
    RecurringEntryDeleteView,
    PostRecurringEntriesView,
    ScheduledReportListView,
    ScheduledReportCreateView,
    ScheduledReportUpdateView,
    ScheduledReportDeleteView,
    TaskMonitorView,
    TaskHistoryView
)

app_name = "scheduled_tasks"

urlpatterns = [
    # Period closing URLs
    path('periods/', 
         PeriodClosingListView.as_view(), 
         name='period_list'),
    
    path('periods/<int:pk>/', 
         PeriodClosingDetailView.as_view(), 
         name='period_detail'),
    
    path('periods/<int:pk>/close/', 
         PeriodClosingView.as_view(), 
         name='period_close'),
    
    # Recurring entry URLs
    path('recurring-entries/', 
         RecurringEntryListView.as_view(), 
         name='recurring_list'),
    
    path('recurring-entries/create/', 
         RecurringEntryCreateView.as_view(), 
         name='recurring_create'),
    
    path('recurring-entries/<int:pk>/edit/', 
         RecurringEntryUpdateView.as_view(), 
         name='recurring_update'),
    
    path('recurring-entries/<int:pk>/delete/', 
         RecurringEntryDeleteView.as_view(), 
         name='recurring_delete'),
    
    path('recurring-entries/post/', 
         PostRecurringEntriesView.as_view(), 
         name='post_recurring'),
    
    # Scheduled report URLs
    path('scheduled-reports/', 
         ScheduledReportListView.as_view(), 
         name='report_list'),
    
    path('scheduled-reports/create/', 
         ScheduledReportCreateView.as_view(), 
         name='report_create'),
    
    path('scheduled-reports/<int:pk>/edit/', 
         ScheduledReportUpdateView.as_view(), 
         name='report_update'),
    
    path('scheduled-reports/<int:pk>/delete/', 
         ScheduledReportDeleteView.as_view(), 
         name='report_delete'),
    
    # Task monitoring URLs
    path('task/<str:task_id>/status/', 
         TaskMonitorView.as_view(), 
         name='task_status'),
    
    path('task-history/', 
         TaskHistoryView.as_view(), 
         name='task_history'),
]
