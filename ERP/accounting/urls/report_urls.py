"""
Report URLs - Phase 3 Task 2

URL patterns for financial reporting:
- Report list
- 6 Report generators
- Export handler
"""

from django.urls import path
from accounting.views.report_views import (
    ReportListView,
    GeneralLedgerView,
    TrialBalanceView,
    ProfitLossView,
    BalanceSheetView,
    CashFlowView,
    AccountsReceivableAgingView,
    AccountsPayableAgingView,
    ReportExportView,
)

app_name = 'accounting_reports'

urlpatterns = [
    # Report list
    path('', ReportListView.as_view(), name='report_list'),
    
    # Individual reports
    path('general-ledger/', GeneralLedgerView.as_view(), name='report_ledger'),
    path('trial-balance/', TrialBalanceView.as_view(), name='report_trial_balance'),
    path('profit-loss/', ProfitLossView.as_view(), name='report_pl'),
    path('balance-sheet/', BalanceSheetView.as_view(), name='report_bs'),
    path('cash-flow/', CashFlowView.as_view(), name='report_cf'),
    path('ar-aging/', AccountsReceivableAgingView.as_view(), name='report_ar_aging'),
    path('ap-aging/', AccountsPayableAgingView.as_view(), name='report_ap_aging'),
    
    # Export handler
    path('export/', ReportExportView.as_view(), name='report_export'),
]
