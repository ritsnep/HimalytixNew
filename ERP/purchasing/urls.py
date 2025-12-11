from django.urls import path

from purchasing import views
from purchasing.views_po import (
    POWorkspaceView,
    POListView,
    POListPageView,
    PODetailView,
    POCreateView,
    POUpdateView,
    POApproveView,
    POSendView,
    POCancelView,
    POLineAddView,
)
from purchasing.views_gr import (
    GRWorkspaceView,
    GRListView,
    GRListPageView,
    GRDetailView,
    GRCreateView,
    GRUpdateView,
    GRPostView,
    GRCancelView,
    GRLineUpdateView,
)
from purchasing.views import reports

app_name = "purchasing"

urlpatterns = [
    # Purchase Orders
    path("pos/", POWorkspaceView.as_view(), name="po_workspace"),
    path("pos/list/", POListView.as_view(), name="po_list"),
    path("pos/table/", POListPageView.as_view(), name="po_table"),
    path("pos/create/", POCreateView.as_view(), name="po_create"),
    path("pos/<int:pk>/", PODetailView.as_view(), name="po_detail"),
    path("pos/<int:pk>/edit/", POUpdateView.as_view(), name="po_edit"),
    path("pos/<int:pk>/approve/", POApproveView.as_view(), name="po_approve"),
    path("pos/<int:pk>/send/", POSendView.as_view(), name="po_send"),
    path("pos/<int:pk>/cancel/", POCancelView.as_view(), name="po_cancel"),
    path("pos/<int:pk>/line/add/", POLineAddView.as_view(), name="po_line_add"),
    
    # Goods Receipts
    path("grs/", GRWorkspaceView.as_view(), name="gr_workspace"),
    path("grs/list/", GRListView.as_view(), name="gr_list"),
    path("grs/table/", GRListPageView.as_view(), name="gr_table"),
    path("grs/create/", GRCreateView.as_view(), name="gr_create"),
    path("grs/<int:pk>/", GRDetailView.as_view(), name="gr_detail"),
    path("grs/<int:pk>/edit/", GRUpdateView.as_view(), name="gr_edit"),
    path("grs/<int:pk>/post/", GRPostView.as_view(), name="gr_post"),
    path("grs/<int:pk>/cancel/", GRCancelView.as_view(), name="gr_cancel"),
    path("grs/line/<int:pk>/update/", GRLineUpdateView.as_view(), name="gr_line_update"),
    
    # Invoices (existing)
    path("", views.workspace, name="workspace"),
    path("invoices/", views.invoice_list, name="invoice-list"),
    path("invoices/new/", views.invoice_form, name="invoice-create"),
    path("invoices/<int:pk>/edit/", views.invoice_form, name="invoice-edit"),
    path("invoices/<int:pk>/detail/", views.invoice_detail, name="invoice-detail"),
    path("invoices/<int:pk>/post/", views.invoice_post, name="invoice-post"),
    path("invoices/<int:pk>/delete/", views.invoice_delete, name="invoice-delete"),
    path("invoices/<int:pk>/reverse/", views.invoice_reverse, name="invoice-reverse"),
    path("invoices/<int:pk>/return/", views.invoice_return, name="invoice-return"),
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
    path("reports/", reports, name="reports"),
    path("invoices/table/", views.invoice_list_page, name="invoice-table"),
    path("landed-cost/table/", views.landed_cost_list_page, name="landed-cost-table"),
]
