from django.urls import path, include, re_path

from accounting.api import dashboard_views as api_dashboard_views
from accounting.views import dashboard_views
from accounting.views import views_import
from accounting.views.analytics_views import PayableDashboardView, ReceivableDashboardView
from accounting.views.audit_log_views import (
    AuditLogListView, AuditLogDetailView, AuditLogSummaryView,
    audit_log_export_csv, audit_log_export_json
)
from ..views import journal_entry, journal_entry_view, voucher_views, voucher_crud_views
from ..views import views_journal_grid as journal_grid_view
from ..views import generic_voucher_views
from ..views import generic_voucher_lookups
from ..views.report_views import (
    ReportListView,
    GeneralLedgerView,
    TrialBalanceView as TrialBalanceReportView,
    ProfitLossView,
    BalanceSheetView as BalanceSheetReportView,
    CashFlowView,
    AccountsReceivableAgingView,
    AccountsPayableAgingView,
    SalesSummaryView,
    InventorySummaryView,
    TaxSummaryView,
    ExpenseSummaryView,
    ReportExportView,
    CustomReportView,
)

# Import from views_list.py
from ..views.views_list import (
     ChartOfAccountTreeListView, FiscalYearListView, CostCenterListView, DepartmentListView,
    AccountTypeListView, GeneralLedgerListView, TaxCodeListView,
    JournalListView
)

# Import from views.py (for reports, general views, and most list/detail views)
from ..views import views
from ..views.views import (
    ReportsListView, TrialBalanceView, IncomeStatementView, BalanceSheetView,
    GeneralLedgerDetailView, VoucherTypeConfigurationView, VoucherEntryView,
    ChartOfAccountFormFieldsView, AccountingPeriodDetailView,  FiscalYearDetailView, AccountingPeriodCloseView, FiscalYearCloseView,JournalTypeDetailView,
    get_next_account_code, JournalEntryView, JournalDetailView, VoucherConfigurationView,
    JournalTypeListView, VoucherModeConfigListView, VoucherModeConfigDetailView,
    VoucherUDFConfigListView,
    CurrencyListView, CurrencyExchangeRateListView, TaxAuthorityListView,
    TaxTypeListView, ProjectListView, AccountingPeriodListView, JournalPostView
)
from ..views.views_list import ChartOfAccountListPartial
from ..views.views_list import ChartOfAccountListView
from ..views import chart_of_account_enhanced
from ..views.currency_bulk_import import (
    CurrencyBulkCreateView as CurrencyBulkImportView,
    CurrencyDemoImportView as CurrencyDemoView,
)

# Import from views_create.py
from ..views.views_create import (
    CostCenterCreateView, DepartmentCreateView, FiscalYearCreateView, JournalCreateView, VoucherModeConfigCreateView,
    VoucherModeDefaultCreateView, VoucherUDFConfigCreateView, ChartOfAccountCreateView,
    AccountTypeCreateView, CurrencyCreateView, CurrencyExchangeRateCreateView,
    TaxAuthorityCreateView, TaxTypeCreateView, ProjectCreateView, AccountingPeriodCreateView,
    JournalTypeCreateView, GeneralLedgerCreateView, TaxCodeCreateView
)

# Import from views_update.py
from ..views.views_update import (
    CostCenterUpdateView, FiscalYearUpdateView, VoucherModeConfigUpdateView,
    VoucherModeDefaultUpdateView, VoucherUDFConfigUpdateView, ChartOfAccountUpdateView,
    AccountTypeUpdateView, CurrencyUpdateView, CurrencyExchangeRateUpdateView,
    TaxAuthorityUpdateView, TaxTypeUpdateView, ProjectUpdateView, AccountingPeriodUpdateView,
    DepartmentUpdateView, JournalTypeUpdateView, JournalUpdateView, GeneralLedgerUpdateView,
    TaxCodeUpdateView
)

# Import from views_delete.py
from ..views.views_delete import (
    AccountingPeriodDeleteView, VoucherModeDefaultDeleteView, ChartOfAccountDeleteView,
    AccountTypeDeleteView, VoucherUDFConfigDeleteView, JournalTypeDeleteView, FiscalYearDeleteView,
    JournalDeleteView, GeneralLedgerDeleteView, CostCenterDeleteView, DepartmentDeleteView,
    CurrencyDeleteView, CurrencyExchangeRateDeleteView, TaxAuthorityDeleteView, TaxTypeDeleteView,
    ProjectDeleteView, TaxCodeDeleteView, VoucherModeConfigDeleteView
)

from ..api import views as api_views
from ..views import journal_entry_view
from ..views import journal_entry_htmx
from ..views import views_chart
from ..views import views_settings
from ..views import journal_check_view
from ..views import views_actions
from ..views import views_api
from ..views import recurring_journal_views
from ..views import views_htmx
from ..views.views_htmx import AccountTypeDependentFieldsHXView
from ..views import wizard
from ..views import purchase_invoice_views, payment_scheduler_views, vendor_statement_views, customer_statement_views, sales_invoice_views, ar_receipt_views, commerce_views, sales_order_views, expense_views
from ..views import sales_invoice_views, ar_receipt_views, commerce_views, sales_order_views
from ..views import delivery_note_views
from ..views.voucher_create_view import (
    VoucherCreateView,
    VoucherCreateHtmxView,
    VoucherAccountLookupHtmxView,
    VoucherTaxCalculationHtmxView,
)

app_name = "accounting"

urlpatterns = [
    
    path('journal-entry-grid/', journal_grid_view.journal_entry_grid, name='journal_entry_grid'),
    path('journal-entry-grid/add-row', journal_grid_view.journal_entry_grid_add_row, name='journal_entry_grid_add_row'),
    path('journal-entry-grid/validate-row', journal_grid_view.journal_entry_grid_validate_row, name='journal_entry_grid_validate_row'),
    path('journal-entry-grid/paste', journal_grid_view.journal_entry_grid_paste, name='journal_entry_grid_paste'),
    path('journal-entry-grid/save', journal_grid_view.journal_entry_grid_save, name='journal_entry_grid_save'),
    path('journal-entry-grid/account-lookup', journal_grid_view.account_lookup, name='journal_entry_grid_account_lookup'),
    # Journal Entry URLs
    path('journal-entry/', journal_entry.journal_entry, name='journal_entry'),
    path('journal-entry/select-config/', journal_entry.journal_select_config, name='journal_select_config'),
    path('journal-entry/save-draft/', journal_entry.journal_save_draft, name='journal_save_draft'),
    path('journal-entry/submit/', journal_entry.journal_submit, name='journal_submit'),
    path('journal-entry/period/validate/', journal_entry.journal_period_validate, name='journal_period_validate'),
    path('journal-entry/approve/', journal_entry.journal_approve, name='journal_approve'),
    path('journal-entry/reject/', journal_entry.journal_reject, name='journal_reject'),
    path('journal-entry/post/', journal_entry.journal_post, name='journal_post'),
    path('journal-entry/config/', journal_entry.journal_config, name='journal_config'),
    path('journal-entry/api/<int:pk>/', journal_entry.journal_entry_data, name='journal_entry_data'),
    path('journal-entry/lookup/accounts/', journal_entry.journal_account_lookup, name='journal_account_lookup'),
    path('journal-entry/lookup/cost-centers/', journal_entry.journal_cost_center_lookup, name='journal_cost_center_lookup'),
    path('journal-entry/lookup/departments/', journal_entry.journal_department_lookup, name='journal_department_lookup'),
    path('journal-entry/lookup/projects/', journal_entry.journal_project_lookup, name='journal_project_lookup'),
    path('journal-entry/lookup/tax-codes/', journal_entry.journal_tax_code_lookup, name='journal_tax_code_lookup'),
    path('journal-entry/lookup/vendors/', journal_entry.journal_vendor_lookup, name='journal_vendor_lookup'),
    path('journal-entry/lookup/customers/', journal_entry.journal_customer_lookup, name='journal_customer_lookup'),
    path('journal-entry/lookup/products/', journal_entry.journal_product_lookup, name='journal_product_lookup'),
    path('journal-entry/resolve-exchange-rate/', journal_entry.resolve_exchange_rate, name='resolve_exchange_rate'),
    path('journal-entry/auto-date/', journal_entry.voucher_entry_auto_date_hx, name='voucher_entry_auto_date_hx'),
    path('journal-entry/approval-actions/', journal_entry.voucher_entry_approval_actions_hx, name='voucher_entry_approval_actions_hx'),
    path('journal-entry/payment-terms/', journal_entry.journal_payment_terms, name='journal_payment_terms'),
    # HTMX partial endpoints (trailing slash optional)
    path('journal-entry/header-partial/', journal_entry.journal_entry_header_partial, name='journal_entry_header_partial'),
    re_path(r'^journal-entry/header-partial/?$', journal_entry.journal_entry_header_partial),
    path('journal-entry/lines-partial/', journal_entry.journal_entry_lines_partial, name='journal_entry_lines_partial'),
    re_path(r'^journal-entry/lines-partial/?$', journal_entry.journal_entry_lines_partial),
    path('journal-entry/side-panel/', journal_entry.journal_entry_side_panel, name='journal_entry_side_panel'),
    re_path(r'^journal-entry/side-panel/?$', journal_entry.journal_entry_side_panel),
    path('journal-entry/row/', journal_entry.journal_entry_row, name='journal_entry_row'),
    path('journal-entry/add-row/', journal_entry.journal_entry_add_row, name='journal_entry_add_row'),
    path('journal-entry/duplicate-row/', journal_entry.journal_entry_row_duplicate, name='journal_entry_row_duplicate'),
    path('journal-entry/delete-row/', journal_entry.journal_entry_row_delete, name='journal_entry_row_delete'),
    path('journal-entry/rows/reorder/', journal_entry.journal_entry_rows_reorder, name='journal_entry_rows_reorder'),
    path('journal-entry/bulk-add/', journal_entry.journal_entry_bulk_add, name='journal_entry_bulk_add'),
    path('journal-entry/imbalance-bar/', journal_entry.journal_entry_imbalance_bar, name='journal_entry_imbalance_bar'),
    path('journal-entry/auto-balance/', journal_entry.journal_auto_balance, name='journal_entry_auto_balance'),
    path('journal-entry/prefs/', journal_entry.journal_ui_preferences, name='journal_ui_preferences'),
    path('journal-entry/prefs/save/', journal_entry.journal_ui_preferences_save, name='journal_ui_preferences_save'),
    path('journal-entry/attachments/upload/', journal_entry.journal_attachment_upload, name='journal_attachment_upload'),
    path('journal-entry/attachments/delete/', journal_entry.journal_attachment_delete, name='journal_attachment_delete'),
    path('journal/new/', journal_entry_htmx.journal_entry_new, name='journal_entry_new'),
    path('journal/header/', journal_entry_htmx.journal_header_partial, name='journal_header_partial'),
    path('journal/lines/', journal_entry_htmx.journal_lines_partial, name='journal_lines_partial'),
    path('journal/lines/add/', journal_entry_htmx.journal_add_line_hx, name='journal_add_line_hx'),
    path('journal/lines/duplicate/', journal_entry_htmx.journal_duplicate_line_hx, name='journal_duplicate_line_hx'),
    path('journal/validate-hx/', journal_entry_htmx.journal_validate_hx, name='journal_validate_hx'),
    path('journal/<int:pk>/', journal_entry_view.JournalEntryDetailView.as_view(), name='journal_entry_detail'),
    path('journal/<int:pk>/edit/', journal_entry_view.JournalEntryUpdateView.as_view(), name='journal_entry_edit'),
    path('journal/validate/', journal_entry_view.JournalEntryValidateView.as_view(), name='journal_entry_validate'),

    path('journal/download-template/', journal_entry_view.download_excel_template, name='download_excel_template'),
    path('journal-entry-htmx-handler/<str:handler>/', journal_entry_view.JournalEntryDetailView.as_view(), name='journal_entry_htmx_handler'),
    path('journal-entry/htmx/get_row_template/', journal_entry_view.JournalEntryRowTemplateView.as_view(), name='journal_entry_row_template'),
    path('journal/<int:journal_id>/line/<int:line_index>/details/', journal_entry_view.JournalLineDetailHXView.as_view(), name='journal_line_details_hx'),

    # Journal URLs
    path('journals/', JournalListView.as_view(), name='journal_list'),
    path('journals/create/', JournalEntryView.as_view(), name='journal_create'),
    path('journals/<int:pk>/', JournalDetailView.as_view(), name='journal_detail'),
    path('journals/<int:pk>/edit/', JournalEntryView.as_view(), name='journal_update'),
    path('journals/<int:pk>/post/', JournalPostView.as_view(), name='journal_post'),
    path('journals/<int:pk>/duplicate/', views_actions.JournalDuplicateView.as_view(), name='journal_duplicate'),
    path('journals/<int:pk>/reverse/', views_actions.JournalReverseView.as_view(), name='journal_reverse'),
    path('journals/<int:pk>/delete/', JournalDeleteView.as_view(), name='journal_delete'),
    path('journals/<int:pk>/audit/', journal_entry_view.JournalAuditTrailView.as_view(), name='journal_audit_trail'),
    path('journals/import/', views_import.JournalImportView.as_view(), name='journal_import'),
    path('journal/import/validate/', views_import.JournalImportValidateView.as_view(), name='journal_import_validate'),
    path('journal/import/process/', views_import.JournalImportProcessView.as_view(), name='journal_import_process'),
    path('journals/<int:journal_id>/save-as-recurring/', recurring_journal_views.RecurringJournalCreateView.as_view(), name='save_as_recurring'),
    
    # Recurring Journal URLs
    path('recurring-journals/', recurring_journal_views.RecurringJournalListView.as_view(), name='recurring-journal-list'),
    path('recurring-journals/create/', recurring_journal_views.RecurringJournalCreateView.as_view(), name='recurring-journal-create'),
    path('recurring-journals/<int:pk>/update/', recurring_journal_views.RecurringJournalUpdateView.as_view(), name='recurring-journal-update'),
    path('recurring-journals/<int:pk>/delete/', recurring_journal_views.RecurringJournalDeleteView.as_view(), name='recurring-journal-delete'),
    
    # General Ledger URLs
    path('general-ledger/', GeneralLedgerListView.as_view(), name='general_ledger_list'),
    path('general-ledger/create/', GeneralLedgerCreateView.as_view(), name='general_ledger_create'),
    path('general-ledger/<int:pk>/', GeneralLedgerDetailView.as_view(), name='general_ledger_detail'),
    path('general-ledger/<int:pk>/edit/', GeneralLedgerUpdateView.as_view(), name='general_ledger_update'),
    path('general-ledger/<int:pk>/delete/', GeneralLedgerDeleteView.as_view(), name='general_ledger_delete'),

    # Voucher Mode URLs
    path('voucher-configs/', VoucherModeConfigListView.as_view(), name='voucher_config_list'),
    path('voucher-configs/create/', VoucherModeConfigCreateView.as_view(), name='voucher_config_create'),
    path('voucher-configs/<int:pk>/', VoucherModeConfigDetailView.as_view(), name='voucher_config_detail'),
    path('voucher-configs/<int:pk>/edit/', VoucherModeConfigUpdateView.as_view(), name='voucher_config_update'),
    path('voucher-configs/<int:pk>/delete/', VoucherModeConfigDeleteView.as_view(), name='voucher_config_delete'),
    
    path('api/v1/voucher-type-configurations/<int:config_id>/', VoucherTypeConfigurationView.as_view(), name='voucher_type_configuration'),
    
    path('voucher-configs/<int:config_id>/defaults/create/', VoucherModeDefaultCreateView.as_view(), name='voucher_default_create'),
    path('voucher-defaults/<int:pk>/edit/', VoucherModeDefaultUpdateView.as_view(), name='voucher_default_update'),
    path('voucher-defaults/<int:pk>/delete/', VoucherModeDefaultDeleteView.as_view(), name='voucher_default_delete'),
    
    # Voucher UDF URLs
    path('voucher-udfs/', VoucherUDFConfigListView.as_view(), name='voucher_udf_list'),
    path('voucher-udfs/create/', VoucherUDFConfigCreateView.as_view(), name='voucher_udf_create'),
    path('voucher-udfs/<int:pk>/edit/', VoucherUDFConfigUpdateView.as_view(), name='voucher_udf_update'),
    path('voucher-udfs/<int:pk>/delete/', VoucherUDFConfigDeleteView.as_view(), name='voucher_udf_delete'),
    
    # New Voucher Configuration System
    path('voucher-configuration/', VoucherConfigurationView.as_view(), name='voucher_field_config'),
    
    path('voucher-entry/', VoucherEntryView.as_view(), name='voucher_entry'),
    path('voucher-entry/list/', voucher_crud_views.VoucherListView.as_view(), name='voucher_entry_list'),
    path('voucher-entry/create/', VoucherCreateView.as_view(), name='voucher_entry_create'),
    path('voucher-entry/create/<str:journal_type>/', VoucherCreateView.as_view(), name='voucher_entry_create_typed'),
    # HTMX helpers for voucher entry
    path('voucher-entry/htmx/add-line/', VoucherCreateHtmxView.as_view(), name='voucher_entry_add_line_hx'),
    path('voucher-entry/htmx/account-lookup/', VoucherAccountLookupHtmxView.as_view(), name='voucher_entry_account_lookup_hx'),
    path('voucher-entry/htmx/tax-calculation/', VoucherTaxCalculationHtmxView.as_view(), name='voucher_entry_tax_calculation_hx'),
    # path('voucher-entry/<int:config_id>/', VoucherEntryView.as_view(), name='voucher_entry_config'),
    path('expenses/new/', expense_views.ExpenseEntryCreateView.as_view(), name='expense_entry_new'),
    path('expenses/ocr/', expense_views.ExpenseReceiptOCRView.as_view(), name='expense_receipt_ocr'),
    path('expenses/ocr/<str:task_id>/status/', expense_views.ExpenseReceiptOCRStatusView.as_view(), name='expense_receipt_ocr_status'),
    
    # Voucher CRUD URLs (order matters - specific routes before generic!)
    path('vouchers/', voucher_views.VoucherListView.as_view(), name='voucher_list'),
    path('vouchers/new/', voucher_crud_views.VoucherCreateView.as_view(), name='voucher_create'),
    path('vouchers/new/<int:config_id>/', voucher_crud_views.VoucherCreateView.as_view(), name='voucher_create_with_config'),
    path('vouchers/wizard/', wizard.VoucherWizardView.as_view(), name='voucher_wizard'),
    path('vouchers/wizard/<int:pk>/', wizard.VoucherWizardView.as_view(), name='voucher_wizard_edit'),
    path('vouchers/<int:pk>/', voucher_crud_views.VoucherDetailView.as_view(), name='voucher_detail'),
    path('vouchers/<int:pk>/edit/', voucher_crud_views.VoucherUpdateView.as_view(), name='voucher_edit'),
    path('vouchers/<int:pk>/delete/', voucher_crud_views.VoucherDeleteView.as_view(), name='voucher_delete'),
    path('vouchers/<int:pk>/duplicate/', voucher_crud_views.VoucherDuplicateView.as_view(), name='voucher_duplicate'),
    path('vouchers/<int:pk>/post/', voucher_crud_views.VoucherPostView.as_view(), name='voucher_post'),
    
    # Generic Voucher URLs
    path('generic-voucher/select/', generic_voucher_views.VoucherTypeSelectionView.as_view(), name='generic_voucher_select'),
    path('generic-voucher/<slug:voucher_code>/create/', generic_voucher_views.GenericVoucherCreateView.as_view(), name='generic_voucher_create'),
    path('generic-voucher/line/', generic_voucher_views.GenericVoucherLineView.as_view(), name='generic_voucher_line'),
        path('generic-voucher/htmx/vendor-lookup/', generic_voucher_lookups.GenericVoucherVendorLookupJsonView.as_view(), name='generic_voucher_vendor_lookup_hx'),
        path('generic-voucher/htmx/customer-lookup/', generic_voucher_lookups.GenericVoucherCustomerLookupJsonView.as_view(), name='generic_voucher_customer_lookup_hx'),
        path('generic-voucher/htmx/product-lookup/', generic_voucher_lookups.GenericVoucherProductLookupJsonView.as_view(), name='generic_voucher_product_lookup_hx'),
    
    # Legacy Voucher Views (kept for backward compatibility)
    path('vouchers/legacy/print/<int:pk>/', voucher_views.VoucherPrintView.as_view(), name='voucher_print'),
    path('vouchers/export/', voucher_views.VoucherExportView.as_view(), name='voucher_export'),
    path('vouchers/import-file/', views_import.JournalImportView.as_view(), name='voucher_import'),
    
    # Fiscal Year URLs
    path('fiscal_year/', FiscalYearCreateView.as_view(), name='fiscal_year_create'),
    path('fiscal_year/list/', FiscalYearListView.as_view(), name='fiscal_year_list'),
    path('fiscal_year/<str:fiscal_year_id>/', FiscalYearUpdateView.as_view(), name='fiscal_year_update'),
    path('fiscal_year/<str:pk>/delete/', FiscalYearDeleteView.as_view(), name='fiscal_year_delete'),
    
    path('fiscal_year/<str:fiscal_year_id>/detail/', FiscalYearDetailView.as_view(), name='fiscal_year_detail'),
    path('fiscal_year/<str:fiscal_year_id>/close/', FiscalYearCloseView.as_view(), name='fiscal_year_close'),
    # Cost Center URLs
    path('cost-centers/', CostCenterListView.as_view(), name='costcenter_list'),
    path('cost-centers/create/', CostCenterCreateView.as_view(), name='costcenter_create'),
    path('cost-centers/<int:pk>/edit/', CostCenterUpdateView.as_view(), name='costcenter_update'),
    path('cost-centers/<int:pk>/delete/', CostCenterDeleteView.as_view(), name='costcenter_delete'),

    # Department URLs
    path('departments/', DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/update/', DepartmentUpdateView.as_view(), name='department_update'),
    path('departments/<int:pk>/delete/', DepartmentDeleteView.as_view(), name='department_delete'),

    # Chart of Accounts URLs
    path('chart-of-accounts/', ChartOfAccountTreeListView.as_view(), name='chart_of_accounts_list'),
    path('chart-of-accounts.hx/', ChartOfAccountListPartial.as_view(), name='chart_of_accounts_list_hx'),
    path('chart-of-accounts/create/', ChartOfAccountCreateView.as_view(), name='chart_of_accounts_create'),
    path('chart-of-accounts/<int:pk>/update/', ChartOfAccountUpdateView.as_view(), name='chart_of_accounts_update'),
    path('chart-of-accounts/<int:pk>/delete/', ChartOfAccountDeleteView.as_view(), name='chart_of_accounts_delete'),
    path('chart-of-accounts/form-fields/', ChartOfAccountFormFieldsView.as_view(), name='chart_of_accounts_form_fields'),
    
    # Enhanced Chart of Accounts - Bulk Import & Demo Data
    path('chart-of-accounts/bulk-create/', chart_of_account_enhanced.ChartOfAccountBulkCreateView.as_view(), name='chart_of_accounts_bulk_create'),
    path('chart-of-accounts/demo-import/', chart_of_account_enhanced.ChartOfAccountDemoImportView.as_view(), name='chart_of_accounts_demo_import'),
    path('chart-of-accounts/demo-preview/', chart_of_account_enhanced.ChartOfAccountDemoPreviewView.as_view(), name='chart_of_accounts_demo_preview'),

    # Account Type URLs
    path('account-types/', AccountTypeListView.as_view(), name='account_type_list'),
    path('account-types/create/', AccountTypeCreateView.as_view(), name='account_type_create'),
    path('account-types/<int:pk>/edit/', AccountTypeUpdateView.as_view(), name='account_type_update'),
    path('account-types/<int:pk>/delete/', AccountTypeDeleteView.as_view(), name='account_type_delete'),

    # Currency URLs
    path('currencies/', CurrencyListView.as_view(), name='currency_list'),
    path('currencies/create/', CurrencyCreateView.as_view(), name='currency_create'),
    path('currencies/bulk-import/', CurrencyBulkImportView.as_view(), name='currency_bulk_import'),
    path('currencies/demo-import/', CurrencyDemoView.as_view(), name='currency_demo_import'),
    path('currencies/demo-preview/', CurrencyDemoView.as_view(), name='currency_demo_preview'),
    path('currencies/<str:currency_code>/edit/', CurrencyUpdateView.as_view(), name='currency_update'),
    path('currencies/<str:currency_code>/delete/', CurrencyDeleteView.as_view(), name='currency_delete'),

    # Currency Exchange Rate URLs
    path('exchange-rates/', CurrencyExchangeRateListView.as_view(), name='exchange_rate_list'),
    path('exchange-rates/create/', CurrencyExchangeRateCreateView.as_view(), name='exchange_rate_create'),
    path('exchange-rates/<int:pk>/edit/', CurrencyExchangeRateUpdateView.as_view(), name='exchange_rate_update'),
    path('exchange-rates/<int:pk>/delete/', CurrencyExchangeRateDeleteView.as_view(), name='exchange_rate_delete'),

    # Tax Authority URLs
    path('tax-authorities/', TaxAuthorityListView.as_view(), name='tax_authority_list'),
    path('tax-authorities/create/', TaxAuthorityCreateView.as_view(), name='tax_authority_create'),
    path('tax-authorities/<int:pk>/edit/', TaxAuthorityUpdateView.as_view(), name='tax_authority_update'),
    path('tax-authorities/<int:pk>/delete/', TaxAuthorityDeleteView.as_view(), name='tax_authority_delete'),

    # Tax Type URLs
    path('tax-types/', TaxTypeListView.as_view(), name='tax_type_list'),
    path('tax-types/create/', TaxTypeCreateView.as_view(), name='tax_type_create'),
    path('tax-types/<int:pk>/edit/', TaxTypeUpdateView.as_view(), name='tax_type_update'),
    path('tax-types/<int:pk>/delete/', TaxTypeDeleteView.as_view(), name='tax_type_delete'),
    path('tax-codes/', TaxCodeListView.as_view(), name='tax_code_list'),
    path('tax-codes/create/', TaxCodeCreateView.as_view(), name='tax_code_create'),
    path('tax-codes/<int:pk>/edit/', TaxCodeUpdateView.as_view(), name='tax_code_update'),
    path('tax-codes/<int:pk>/delete/', TaxCodeDeleteView.as_view(), name='tax_code_delete'),

    # Project URLs
    path('projects/', ProjectListView.as_view(), name='project_list'),
    path('projects/create/', ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/edit/', ProjectUpdateView.as_view(), name='project_update'),
    path('projects/<int:pk>/delete/', ProjectDeleteView.as_view(), name='project_delete'),

    # Accounting Period URLs
    path('accounting-periods/', AccountingPeriodListView.as_view(), name='accounting_period_list'),
    path('accounting-periods/create/', AccountingPeriodCreateView.as_view(), name='accounting_period_create'),
    path('accounting-periods/<int:period_id>/', AccountingPeriodDetailView.as_view(), name='accounting_period_detail'),
    path('accounting-periods/<int:period_id>/edit/', AccountingPeriodUpdateView.as_view(), name='accounting_period_update'),
    path('accounting-periods/<int:pk>/delete/', AccountingPeriodDeleteView.as_view(), name='accounting_period_delete'),

    path('accounting-periods/<int:period_id>/close/', AccountingPeriodCloseView.as_view(), name='accounting_period_close'),
    # Journal Type URLs
    path('journal-types/', JournalTypeListView.as_view(), name='journal_type_list'),
    path('journal-types/create/', JournalTypeCreateView.as_view(), name='journal_type_create'),
    path('journal-types/<int:journal_type_id>/', JournalTypeDetailView.as_view(), name='journal_type_detail'),
    path('journal-types/<int:journal_type_id>/edit/', JournalTypeUpdateView.as_view(), name='journal_type_update'),
    path('journal-types/<int:journal_type_id>/delete/', JournalTypeDeleteView.as_view(), name='journal_type_delete'),

    # Financial Reports URLs (Legacy)
    path('reports/', ReportsListView.as_view(), name='reports_list'),
    path('reports/trial-balance/', TrialBalanceView.as_view(), name='trial_balance'),
    path('reports/income-statement/', IncomeStatementView.as_view(), name='income_statement'),
    path('reports/balance-sheet/', BalanceSheetView.as_view(), name='balance_sheet'),
    
    # Advanced Reports URLs (Phase 3 Task 2)
    path('advanced-reports/', ReportListView.as_view(), name='report_list'),
    path('advanced-reports/general-ledger/', GeneralLedgerView.as_view(), name='report_ledger'),
    path('advanced-reports/trial-balance/', TrialBalanceReportView.as_view(), name='report_trial_balance'),
    path('advanced-reports/profit-loss/', ProfitLossView.as_view(), name='report_pl'),
    path('advanced-reports/balance-sheet/', BalanceSheetReportView.as_view(), name='report_bs'),
    path('advanced-reports/cash-flow/', CashFlowView.as_view(), name='report_cf'),
    path('advanced-reports/ar-aging/', AccountsReceivableAgingView.as_view(), name='report_ar_aging'),
    path('advanced-reports/ap-aging/', AccountsPayableAgingView.as_view(), name='report_ap_aging'),
    path('advanced-reports/sales-summary/', SalesSummaryView.as_view(), name='report_sales_summary'),
    path('advanced-reports/inventory-summary/', InventorySummaryView.as_view(), name='report_inventory_summary'),
    path('advanced-reports/tax-summary/', TaxSummaryView.as_view(), name='report_tax_summary'),
    path('advanced-reports/expense-summary/', ExpenseSummaryView.as_view(), name='report_expense_summary'),
    path('advanced-reports/custom/<slug:code>/', CustomReportView.as_view(), name='custom_report'),
    path('advanced-reports/export/', ReportExportView.as_view(), name='report_export'),
    path('receivable-dashboard/', ReceivableDashboardView.as_view(), name='receivable_dashboard'),
    path('payable-dashboard/', PayableDashboardView.as_view(), name='payable_dashboard'),

    # Vendor Billing / Accounts Payable
    path('vendor-bills/new/', purchase_invoice_views.VendorBillCreateView.as_view(), name='vendor_bill_create'),
    path('vendor-bills/line-row/', purchase_invoice_views.VendorBillLineRowView.as_view(), name='vendor_bill_line_row'),
    path('vendor-bills/vendor-summary/', purchase_invoice_views.VendorSummaryHXView.as_view(), name='vendor_summary_hx'),
    path('vendor-payments/scheduler/', payment_scheduler_views.PaymentSchedulerView.as_view(), name='payment_scheduler'),
    path('vendor-payments/statement/', vendor_statement_views.VendorStatementView.as_view(), name='vendor_statement'),
    path('customer-payments/statement/', customer_statement_views.CustomerStatementView.as_view(), name='customer_statement'),
    path('sales-invoices/', sales_invoice_views.SalesInvoiceListView.as_view(), name='sales_invoice_list'),
    path('sales-invoices/new/', sales_invoice_views.SalesInvoiceCreateView.as_view(), name='sales_invoice_create'),
    path('delivery-notes/', delivery_note_views.DeliveryNoteListView.as_view(), name='delivery_note_list'),
    path('delivery-notes/new/', delivery_note_views.DeliveryNoteCreateView.as_view(), name='delivery_note_create'),
    path('delivery-notes/<int:pk>/print/', delivery_note_views.DeliveryNotePrintView.as_view(), name='delivery_note_print'),
    path('delivery-notes/<int:pk>/invoice/', delivery_note_views.DeliveryNoteInvoiceCreateView.as_view(), name='delivery_note_invoice_create'),
    path('sales-orders/', sales_order_views.SalesOrderListView.as_view(), name='sales_order_list'),
    path('sales-orders/new/', sales_order_views.SalesOrderCreateView.as_view(), name='sales_order_create'),
    path('sales-orders/<int:pk>/action/', sales_order_views.SalesOrderActionView.as_view(), name='sales_order_action'),
    path('sales-orders/availability/', sales_order_views.SalesOrderAvailabilityHXView.as_view(), name='sales_order_availability'),
    path('ar-receipts/', ar_receipt_views.ARReceiptListView.as_view(), name='ar_receipt_list'),
    path('ar-receipts/new/', ar_receipt_views.ARReceiptCreateView.as_view(), name='ar_receipt_create'),
    path('ap-payments/', commerce_views.APPaymentListView.as_view(), name='ap_payment_list'),
    path('ap-payments/new/', commerce_views.APPaymentCreateView.as_view(), name='ap_payment_create'),
    path('ap-payments/<int:pk>/edit/', commerce_views.APPaymentUpdateView.as_view(), name='ap_payment_edit'),
    path('customers/', commerce_views.CustomerListView.as_view(), name='customer_list'),
    path('customers/new/', commerce_views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/edit/', commerce_views.CustomerUpdateView.as_view(), name='customer_edit'),
    path('vendors/', commerce_views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/new/', commerce_views.VendorCreateView.as_view(), name='vendor_create'),
    path('vendors/<int:pk>/edit/', commerce_views.VendorUpdateView.as_view(), name='vendor_edit'),

    # AJAX/HTMX URLs
    path('ajax/get-next-account-code/', get_next_account_code, name='get_next_account_code'),
    path('htmx/lookup/<str:model_name>/', views_htmx.LookupHXView.as_view(), name='htmx_lookup'),
    path('htmx/account-types/dependent-fields/', AccountTypeDependentFieldsHXView.as_view(), name='account_type_dependent_fields'),

    # Voucher Settings URL
    path('voucher-settings/', views_settings.VoucherSettingsView.as_view(), name='voucher_settings'),
    path('voucher-settings/diff/', views_settings.VoucherSettingsDiffView.as_view(), name='voucher_settings_diff'),
    path('voucher-settings/rollback/', views_settings.VoucherSettingsRollbackView.as_view(), name='voucher_settings_rollback'),

    # Chart of Accounts Tree URLs
    path('chart-of-accounts/tree/', views_chart.ChartOfAccountTreeListView.as_view(), name='chart_of_accounts_tree'),
    path('chart-of-accounts/tree/api/', views_chart.ChartOfAccountTreeAPI.as_view(), name='chart_of_accounts_tree_api'),
    path('chart-of-accounts/tree/quick-create/', views_chart.ChartOfAccountQuickCreate.as_view(), name='chart_of_accounts_quick_create'),
    path('chart-of-accounts/tree/validate/', views_chart.ChartOfAccountValidateHierarchy.as_view(), name='chart_of_accounts_validate_hierarchy'),
    path('journals/entry/', journal_entry_view.JournalEntryDetailView.as_view(), name='journal_entry_legacy'),
    path('journal-entry/upload-receipt/', journal_entry_view.UploadReceiptView.as_view(), name='upload_receipt'),
    path('journals/config-change/', journal_entry_view.JournalConfigChangeView.as_view(), name='voucher_config_change'),
    path('journal/header-form/', journal_entry_view.JournalHeaderFormView.as_view(), name='journal_header_form'),
    path('journal/new-line/', journal_entry_view.JournalNewLineView.as_view(), name='journal_new_line'),
    path('journal/update-line/', journal_entry_view.JournalUpdateLineView.as_view(), name='journal_update_line'),
    path('journal/validate-line/', journal_entry_view.JournalValidateLineView.as_view(), name='journal_validate_line'),
    path('journals/add-line/',
         journal_entry_view.JournalLineAddView.as_view(),
         name='journal_add_line'),
    path('journals/validate/', journal_entry_view.ValidateJournalEntryView.as_view(), name='journal_validate'),
    path('journal/check-date/', journal_entry_view.JournalCheckDateView.as_view(), name='journal_check_date'),
    path('journals/background-validate/', journal_entry_view.ValidateJournalEntryView.as_view(), name='journal_background_validate'),
    path('journals/save/',journal_entry_view.JournalSaveView.as_view(),
         name='journal_save'),
          
    path('journals/post/<int:pk>/', JournalPostView.as_view(), name='journal_post'),
    path('journals/check/<int:pk>/', journal_check_view.JournalCheckView.as_view(), name='journal_check'),
    path('journals/validate-journal/', journal_entry_view.ValidateJournalEntryView.as_view(), name='validate_journal'),
    path('journal/ocr/', journal_entry_view.JournalOCRView.as_view(), name='journal_ocr'),
    path('api/v1/journals/suggest/', api_views.suggest_journal_entries, name='suggest_journal_entries'),
    path('api/v1/journals/line-suggest/', api_views.get_line_suggestions, name='get_line_suggestions'),

]

urlpatterns += [
    path('api/', include('accounting.api.urls')),
    path('api/compliance/vat-summary/', api_dashboard_views.vat_summary, name='compliance_vat_summary'),
    path('api/compliance/nfrs-schedule/', api_dashboard_views.nfrs_schedule, name='compliance_nfrs_schedule'),
    path('dashboard/', dashboard_views.DashboardView.as_view(), name='dashboard'),
    path('compliance/', dashboard_views.ComplianceView.as_view(), name='compliance'),
]

# API URLs
urlpatterns += [
    path('api/v1/validate-field/', views_api.ValidateFieldView.as_view(), name='validate_field'),
    path('api/v1/journals/suggest/', api_views.suggest_journal_entries, name='suggest_journal_entries'),
    path('api/v1/journals/line-suggest/', api_views.get_line_suggestions, name='get_line_suggestions'),
    path('api/v1/validate-field/', api_views.validate_field, name='validate_field'),
]
urlpatterns += [
    path('api/v1/journals/bulk-action/', api_views.JournalBulkActionView.as_view(), name='journal_bulk_action'),
]

# Import/Export URLs (Phase 3 Task 3)
urlpatterns += [
    path('', include('accounting.urls.import_export_urls')),
    
    # Audit Log URLs
    path('audit-logs/', AuditLogListView.as_view(), name='audit_log_list'),
    path('audit-logs/<int:pk>/', AuditLogDetailView.as_view(), name='audit_log_detail'),
    path('audit-logs/summary/', AuditLogSummaryView.as_view(), name='audit_log_summary'),
    path('audit-logs/export/csv/', audit_log_export_csv, name='audit_log_export_csv'),
    path('audit-logs/export/json/', audit_log_export_json, name='audit_log_export_json'),
]

# Scheduled Tasks URLs (Phase 3 Task 4)
# TODO: Uncomment when RecurringEntry and ScheduledReport models are implemented
# urlpatterns += [
#     path('', include('accounting.urls.scheduled_task_urls')),
# ]

# i18n URLs (Phase 3 Task 6)
urlpatterns += [
    path('', include('accounting.urls.i18n_urls')),
]
