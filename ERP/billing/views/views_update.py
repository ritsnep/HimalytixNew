# billing/views/views_update.py
"""Update views for billing models"""
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from usermanagement.mixins import UserOrganizationMixin
from ..forms import (
    SubscriptionPlanForm, SubscriptionForm, SubscriptionInvoiceForm,
    DeferredRevenueForm, MilestoneRevenueForm, SubscriptionUsageForm
)
from ..models import SubscriptionPlan, Subscription, SubscriptionInvoice, DeferredRevenue, MilestoneRevenue, SubscriptionUsage


class SubscriptionPlanUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    template_name = 'billing/subscriptionplan_form.html'
    permission_required = 'billing.change_subscriptionplan'
    success_url = reverse_lazy('billing:subscriptionplan_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription Plan "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class SubscriptionUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'billing/subscription_form.html'
    permission_required = 'billing.change_subscription'
    success_url = reverse_lazy('billing:subscription_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription "{form.instance.subscription_number}" updated successfully.')
        return super().form_valid(form)


class SubscriptionInvoiceUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = SubscriptionInvoice
    form_class = SubscriptionInvoiceForm
    template_name = 'billing/subscriptioninvoice_form.html'
    permission_required = 'billing.change_subscriptioninvoice'
    success_url = reverse_lazy('billing:subscriptioninvoice_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription Invoice "{form.instance.invoice_number}" updated successfully.')
        return super().form_valid(form)


class DeferredRevenueUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = DeferredRevenue
    form_class = DeferredRevenueForm
    template_name = 'billing/deferredrevenue_form.html'
    permission_required = 'billing.change_deferredrevenue'
    success_url = reverse_lazy('billing:deferredrevenue_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Deferred Revenue "{form.instance.deferred_revenue_number}" updated successfully.')
        return super().form_valid(form)


class MilestoneRevenueUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = MilestoneRevenue
    form_class = MilestoneRevenueForm
    template_name = 'billing/milestonerevenue_form.html'
    permission_required = 'billing.change_milestonerevenue'
    success_url = reverse_lazy('billing:milestonerevenue_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Milestone Revenue "{form.instance.milestone_name}" updated successfully.')
        return super().form_valid(form)


class SubscriptionUsageUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = SubscriptionUsage
    form_class = SubscriptionUsageForm
    template_name = 'billing/subscriptionusage_form.html'
    permission_required = 'billing.change_subscriptionusage'
    success_url = reverse_lazy('billing:subscriptionusage_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Subscription Usage record updated successfully.')
        return super().form_valid(form)
