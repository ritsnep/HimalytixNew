# billing/views/views_list.py
"""List views for billing models"""
from django.urls import reverse_lazy
from .base_views import BaseListView
from ..models import SubscriptionPlan, Subscription, SubscriptionInvoice, DeferredRevenue, MilestoneRevenue, SubscriptionUsage


class SubscriptionPlanListView(BaseListView):
    model = SubscriptionPlan
    template_name = 'billing/subscriptionplan_list.html'
    context_object_name = 'plans'
    permission_required = ('billing', 'subscriptionplan', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('billing:subscriptionplan_create')
        return context


class SubscriptionListView(BaseListView):
    model = Subscription
    template_name = 'billing/subscription_list.html'
    context_object_name = 'subscriptions'
    permission_required = ('billing', 'subscription', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('billing:subscription_create')
        return context


class SubscriptionInvoiceListView(BaseListView):
    model = SubscriptionInvoice
    template_name = 'billing/subscriptioninvoice_list.html'
    context_object_name = 'invoices'
    permission_required = ('billing', 'subscriptioninvoice', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('billing:subscriptioninvoice_create')
        return context


class DeferredRevenueListView(BaseListView):
    model = DeferredRevenue
    template_name = 'billing/deferredrevenue_list.html'
    context_object_name = 'deferred_revenues'
    permission_required = ('billing', 'deferredrevenue', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('billing:deferredrevenue_create')
        return context


class MilestoneRevenueListView(BaseListView):
    model = MilestoneRevenue
    template_name = 'billing/milestonerevenue_list.html'
    context_object_name = 'milestones'
    permission_required = ('billing', 'milestonerevenue', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('billing:milestonerevenue_create')
        return context


class SubscriptionUsageListView(BaseListView):
    model = SubscriptionUsage
    template_name = 'billing/subscriptionusage_list.html'
    context_object_name = 'usage_records'
    permission_required = ('billing', 'subscriptionusage', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('billing:subscriptionusage_create')
        return context
