"""
URL configuration for HTMX Sales Invoice.

Routes are namespaced under ``vouchers_sales_invoice`` so they can
coexist alongside other accounting routes. The primary page is
``/vouchers/sales-invoice/`` which accepts an optional draft ID as
a slug. All HTMX actions post back to endpoints under this path.
"""

from django.urls import path

from . import views

app_name = "vouchers_sales_invoice"

urlpatterns = [
    # Primary entry point; optional draft_id slug
    path("", views.new, name="new"),
    path("<uuid:draft_id>/", views.new, name="existing"),
    # HTMX actions
    path("<uuid:draft_id>/recalc/", views.recalc, name="recalc"),
    path("<uuid:draft_id>/add-line/", views.add_line, name="add_line"),
    path(
        "<uuid:draft_id>/delete-line/<uuid:line_id>/",
        views.delete_line,
        name="delete_line",
    ),
    path("<uuid:draft_id>/add-receipt/", views.add_receipt, name="add_receipt"),
    path(
        "<uuid:draft_id>/delete-receipt/<uuid:receipt_id>/",
        views.delete_receipt,
        name="delete_receipt",
    ),
    path("<uuid:draft_id>/buyer-info/", views.buyer_info, name="buyer_info"),
    path(
        "<uuid:draft_id>/date-bs-to-ad/",
        views.date_bs_to_ad,
        name="date_bs_to_ad",
    ),
    path(
        "<uuid:draft_id>/date-ad-to-bs/",
        views.date_ad_to_bs,
        name="date_ad_to_bs",
    ),
    path(
        "<uuid:draft_id>/columns-pref/",
        views.columns_pref,
        name="columns_pref",
    ),
    path(
        "<uuid:draft_id>/apply-order/",
        views.apply_order,
        name="apply_order",
    ),
    path(
        "<uuid:draft_id>/refetch-no/",
        views.refetch_no,
        name="refetch_no",
    ),
    path("<uuid:draft_id>/save/", views.save, name="save"),
    path("<uuid:draft_id>/cancel/", views.cancel, name="cancel"),
]
