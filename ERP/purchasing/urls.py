from django.urls import path

from purchasing import views

app_name = "purchasing"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("invoices/", views.invoice_list, name="invoice-list"),
    path("invoices/new/", views.invoice_form, name="invoice-create"),
    path("invoices/<int:pk>/edit/", views.invoice_form, name="invoice-edit"),
    path("invoices/<int:pk>/detail/", views.invoice_detail, name="invoice-detail"),
    path("invoices/<int:pk>/post/", views.invoice_post, name="invoice-post"),
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
]
