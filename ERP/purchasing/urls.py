from django.urls import path

from purchasing import views, unified_views
from purchasing.views import reports

app_name = "purchasing"

urlpatterns = [
    # ===== UNIFIED WORKFLOW ROUTES (PRODUCTION) =====
    
    # Purchase Orders - Unified Form
    path("orders/new/", unified_views.po_unified_form, name="po_unified_create"),
    path("orders/<int:pk>/edit/", unified_views.po_unified_form, name="po_unified_edit"),
    path("orders/<int:pk>/", unified_views.po_detail, name="po_detail"),
    path("orders/<int:pk>/approve/", unified_views.po_approve, name="po_unified_approve"),
    path("orders/<int:pk>/send/", unified_views.po_send, name="po_unified_send"),
    path("orders/<int:pk>/cancel/", unified_views.po_cancel, name="po_unified_cancel"),
    
    # Goods Receipts - Unified Form
    path("receipts/new/", unified_views.gr_unified_form, name="gr_unified_create"),
    path("receipts/<int:pk>/edit/", unified_views.gr_unified_form, name="gr_unified_edit"),
    path("receipts/<int:pk>/", unified_views.gr_detail, name="gr_detail"),
    path("receipts/<int:pk>/inspect/", unified_views.gr_inspect, name="gr_unified_inspect"),
    path("receipts/<int:pk>/post/", unified_views.gr_post, name="gr_unified_post"),
    path("receipts/<int:pk>/cancel/", unified_views.gr_cancel, name="gr_unified_cancel"),
    
    # Purchase Returns - Unified Form
    path("returns/new/", unified_views.pr_unified_form, name="pr_unified_create"),
    path("returns/<int:pk>/", unified_views.pr_unified_form, name="pr_unified_edit"),
    path("invoices/<int:from_invoice_id>/return/", unified_views.pr_unified_form, name="pr_from_invoice"),
    
    # Landed Cost - Unified Form
    path("invoices/<int:invoice_id>/landed-cost/new/", unified_views.landed_cost_unified_form, name="landed_cost_unified_create"),
    path("invoices/<int:invoice_id>/landed-cost/<int:doc_id>/edit/", unified_views.landed_cost_unified_form, name="landed_cost_unified_edit"),
    path("landed-cost/<int:doc_id>/allocate/", unified_views.landed_cost_allocate, name="landed-cost-allocate"),
    path("landed-cost/<int:doc_id>/delete/", unified_views.landed_cost_delete, name="landed-cost-delete"),
    
    # ===== LEGACY DISPLAY ROUTES (kept for backward compatibility, will be deprecated) =====
    # These list/table views redirect to the unified forms above
    
    # Purchase Invoices (Legacy - main workspace)
    path("", views.workspace, name="workspace"),
    path("invoices/", views.invoice_list, name="invoice-list"),
    path("invoices/new/", views.invoice_form, name="invoice-create"),
    path("invoices/<int:pk>/edit/", views.invoice_form, name="invoice-edit"),
    path("invoices/<int:pk>/detail/", views.invoice_detail, name="invoice-detail"),
    path("invoices/<int:pk>/post/", views.invoice_post, name="invoice-post"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice-delete"),
    path("invoices/<int:pk>/reverse/", views.invoice_reverse, name="invoice-reverse"),
    path("invoices/<int:pk>/return/", views.invoice_return, name="invoice-return"),
    path("invoices/table/", views.invoice_list_page, name="invoice-table"),
    path("invoices/recalc/", views.invoice_recalc, name="invoice-recalc"),
    path("invoices/validate/", views.invoice_validate, name="invoice-validate"),
    
    # Landed Cost (Legacy)
    path(
        "landed-cost/<int:invoice_id>/new/",
        views.landed_cost_form,
        name="landed-cost-create",
    ),
    path(
        "landed-cost/<int:invoice_id>/<int:doc_id>/edit/",
        views.landed_cost_form,
        name="landed-cost-edit",
    ),
    path(
        "landed-cost/<int:doc_id>/apply/",
        views.landed_cost_apply,
        name="landed-cost-apply",
    ),
    path("landed-cost/table/", views.landed_cost_list_page, name="landed-cost-table"),
    
    # PO and GR Legacy Views (kept as fallback)
    path("pos/table/", views.po_list_page_legacy, name="po_table"),
    path("grs/table/", views.gr_list_page_legacy, name="gr_table"),
    
    # Reports
    path("reports/", reports, name="reports"),
]
