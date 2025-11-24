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

# router = DefaultRouter()  # API router commented out until viewsets are created
# router.register(r"invoices", InvoiceViewSet, basename="billing-invoice")
# router.register(r"notes", CreditDebitNoteViewSet, basename="billing-note")
# router.register(r"logs", AuditLogViewSet, basename="billing-log")

urlpatterns = [
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
    path('invoices/create/', SubscriptionInvoiceCreateView.as_view(), name='subscriptioninvoice_create'),
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
