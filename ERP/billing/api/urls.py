# billing/api/urls.py
"""
URL routing for Billing API endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SubscriptionPlanViewSet, UsageTierViewSet, SubscriptionViewSet,
    SubscriptionUsageViewSet, SubscriptionInvoiceViewSet,
    DeferredRevenueViewSet, DeferredRevenueScheduleViewSet,
    MilestoneRevenueViewSet
)

router = DefaultRouter()

router.register(r'subscription-plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'usage-tiers', UsageTierViewSet, basename='usage-tier')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'subscription-usage', SubscriptionUsageViewSet, basename='subscription-usage')
router.register(r'subscription-invoices', SubscriptionInvoiceViewSet, basename='subscription-invoice')
router.register(r'deferred-revenue', DeferredRevenueViewSet, basename='deferred-revenue')
router.register(r'deferred-revenue-schedule', DeferredRevenueScheduleViewSet, basename='deferred-revenue-schedule')
router.register(r'milestone-revenue', MilestoneRevenueViewSet, basename='milestone-revenue')

urlpatterns = [
    path('', include(router.urls)),
]
