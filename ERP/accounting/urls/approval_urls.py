"""
Approval Workflow URLs - Phase 3 Task 1

URL patterns for approval workflow views.
"""

from django.urls import path
from accounting.views.approval_workflow import (
    ApprovalQueueView,
    VoucherApproveView,
    VoucherRejectView,
    ApprovalHistoryView,
    ApprovalDashboardView,
)

app_name = 'approval'

urlpatterns = [
    # Approval Queue
    path(
        'queue/',
        ApprovalQueueView.as_view(),
        name='approval_queue'
    ),
    
    # Dashboard
    path(
        'dashboard/',
        ApprovalDashboardView.as_view(),
        name='approval_dashboard'
    ),
    
    # Approval Actions
    path(
        '<int:journal_id>/approve/',
        VoucherApproveView.as_view(),
        name='approve_journal'
    ),
    path(
        '<int:journal_id>/reject/',
        VoucherRejectView.as_view(),
        name='reject_journal'
    ),
    
    # History
    path(
        '<int:pk>/history/',
        ApprovalHistoryView.as_view(),
        name='approval_history'
    ),
]
