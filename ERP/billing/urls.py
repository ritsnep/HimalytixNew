from django.urls import include, path
from rest_framework.routers import DefaultRouter
# from .views import AuditLogViewSet, CreditDebitNoteViewSet, InvoiceViewSet  # Not yet created
from .views import (
    SubscriptionPlanListView, SubscriptionPlanCreateView, SubscriptionPlanUpdateView,
    SubscriptionListView, SubscriptionCreateView, SubscriptionUpdateView,
    SubscriptionInvoiceListView, SubscriptionInvoiceCreateView, SubscriptionInvoiceUpdateView,
    DeferredRevenueListView, DeferredRevenueCreateView, DeferredRevenueUpdateView,
    MilestoneRevenueListView, MilestoneRevenueCreateView, MilestoneRevenueUpdateView,
    SubscriptionUsageListView, SubscriptionUsageCreateView, SubscriptionUsageUpdateView,
)

app_name = "billing"

# HTMX invoice entry helpers
from . import invoice_entry_htmx

# Sales invoice pages and actions (one-off invoices)
from .invoice_entry_htmx import (
    invoice_list, invoice_pdf, submit_to_ird, cancel_invoice, export_tally
)

# router = DefaultRouter()  # API router commented out until viewsets are created
# router.register(r"invoices", InvoiceViewSet, basename="billing-invoice")
# router.register(r"notes", CreditDebitNoteViewSet, basename="billing-note")
# router.register(r"logs", AuditLogViewSet, basename="billing-log")

urlpatterns = [
    # One-off sales invoice list and actions
    path('invoices/', invoice_list, name='invoice_list'),
    path('invoices/<int:invoice_id>/pdf/', invoice_pdf, name='invoice_pdf'),
    path('invoices/<int:invoice_id>/submit-ird/', submit_to_ird, name='submit_to_ird'),
    path('invoices/<int:invoice_id>/cancel/', cancel_invoice, name='cancel_invoice'),
    path('invoices/export/tally/', export_tally, name='export_tally'),
    # API routes (commented out until viewsets are created)
    # path("api/", include(router.urls)),
    
    # Subscription Plan URLs
    path('plans/', SubscriptionPlanListView.as_view(), name='subscriptionplan_list'),
    path('plans/create/', SubscriptionPlanCreateView.as_view(), name='subscriptionplan_create'),
    path('plans/<int:pk>/edit/', SubscriptionPlanUpdateView.as_view(), name='subscriptionplan_update'),
    
    # Subscription URLs
    path('subscriptions/', SubscriptionListView.as_view(), name='subscription_list'),
    path('subscriptions/create/', SubscriptionCreateView.as_view(), name='subscription_create'),
    path('subscriptions/<int:pk>/edit/', SubscriptionUpdateView.as_view(), name='subscription_update'),
    
    # Subscription Invoice URLs
    path('invoices/', SubscriptionInvoiceListView.as_view(), name='subscriptioninvoice_list'),
    # Map the common plural create path to the one-off HTMX invoice entry (used by UI)
    path('invoices/create/', invoice_entry_htmx.invoice_create, name='invoice_create'),
    # Keep the subscription-specific create view available under a namespaced path
    path('invoices/create/subscription/', SubscriptionInvoiceCreateView.as_view(), name='subscriptioninvoice_create'),
    path('invoices/<int:pk>/edit/', SubscriptionInvoiceUpdateView.as_view(), name='subscriptioninvoice_update'),
    
    # Deferred Revenue URLs
    path('deferred-revenue/', DeferredRevenueListView.as_view(), name='deferredrevenue_list'),
    path('deferred-revenue/create/', DeferredRevenueCreateView.as_view(), name='deferredrevenue_create'),
    path('deferred-revenue/<int:pk>/edit/', DeferredRevenueUpdateView.as_view(), name='deferredrevenue_update'),
    
    # Milestone Revenue URLs
    path('milestones/', MilestoneRevenueListView.as_view(), name='milestonerevenue_list'),
    path('milestones/create/', MilestoneRevenueCreateView.as_view(), name='milestonerevenue_create'),
    path('milestones/<int:pk>/edit/', MilestoneRevenueUpdateView.as_view(), name='milestonerevenue_update'),
    
    # Subscription Usage URLs
    path('usage/', SubscriptionUsageListView.as_view(), name='subscriptionusage_list'),
    path('usage/create/', SubscriptionUsageCreateView.as_view(), name='subscriptionusage_create'),
    path('usage/<int:pk>/edit/', SubscriptionUsageUpdateView.as_view(), name='subscriptionusage_update'),
]

# Invoice entry (HTMX) views — lightweight entry points for one-off invoices
from . import invoice_entry_htmx

urlpatterns += [
    path('invoice/create/', invoice_entry_htmx.invoice_create, name='invoice_create'),
    path('invoice/<int:invoice_id>/', invoice_entry_htmx.invoice_detail, name='invoice_detail'),
    path('invoice/save/', invoice_entry_htmx.invoice_save, name='invoice_save'),

    # HTMX endpoints for dynamic invoice entry
    path('htmx/customer-search/', invoice_entry_htmx.customer_search, name='customer_search'),
    path('htmx/product-search/', invoice_entry_htmx.product_search, name='product_search'),
    path('htmx/add-line/', invoice_entry_htmx.add_invoice_line, name='add_invoice_line'),
    path('htmx/calculate-line/', invoice_entry_htmx.calculate_line_total, name='calculate_line_total'),
    path('htmx/calculate-total/', invoice_entry_htmx.calculate_invoice_total, name='calculate_invoice_total'),
]
