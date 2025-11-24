# billing/views/views_create.py
"""Create views for billing models"""
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView
from usermanagement.mixins import UserOrganizationMixin
from accounting.models import AutoIncrementCodeGenerator
from ..forms import (
    SubscriptionPlanForm, SubscriptionForm, SubscriptionInvoiceForm,
    DeferredRevenueForm, MilestoneRevenueForm, SubscriptionUsageForm
)
from ..models import SubscriptionPlan, Subscription, SubscriptionInvoice, DeferredRevenue, MilestoneRevenue, SubscriptionUsage


class SubscriptionPlanCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    template_name = 'billing/subscriptionplan_form.html'
    permission_required = 'billing.add_subscriptionplan'
    success_url = reverse_lazy('billing:subscriptionplan_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(SubscriptionPlan, 'code', organization=organization, prefix='PLAN')
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription Plan "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class SubscriptionCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'billing/subscription_form.html'
    permission_required = 'billing.add_subscription'
    success_url = reverse_lazy('billing:subscription_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(Subscription, 'subscription_number', organization=organization, prefix='SUB')
            initial['subscription_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription "{form.instance.subscription_number}" created successfully.')
        return super().form_valid(form)


class SubscriptionInvoiceCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = SubscriptionInvoice
    form_class = SubscriptionInvoiceForm
    template_name = 'billing/subscriptioninvoice_form.html'
    permission_required = 'billing.add_subscriptioninvoice'
    success_url = reverse_lazy('billing:subscriptioninvoice_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(SubscriptionInvoice, 'invoice_number', organization=organization, prefix='SINV')
            initial['invoice_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription Invoice "{form.instance.invoice_number}" created successfully.')
        return super().form_valid(form)


class DeferredRevenueCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = DeferredRevenue
    form_class = DeferredRevenueForm
    template_name = 'billing/deferredrevenue_form.html'
    permission_required = 'billing.add_deferredrevenue'
    success_url = reverse_lazy('billing:deferredrevenue_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(DeferredRevenue, 'deferred_revenue_number', organization=organization, prefix='DREV')
            initial['deferred_revenue_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Deferred Revenue "{form.instance.deferred_revenue_number}" created successfully.')
        return super().form_valid(form)


class MilestoneRevenueCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = MilestoneRevenue
    form_class = MilestoneRevenueForm
    template_name = 'billing/milestonerevenue_form.html'
    permission_required = 'billing.add_milestonerevenue'
    success_url = reverse_lazy('billing:milestonerevenue_list')

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Milestone Revenue "{form.instance.milestone_name}" created successfully.')
        return super().form_valid(form)


class SubscriptionUsageCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = SubscriptionUsage
    form_class = SubscriptionUsageForm
    template_name = 'billing/subscriptionusage_form.html'
    permission_required = 'billing.add_subscriptionusage'
    success_url = reverse_lazy('billing:subscriptionusage_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        # SubscriptionUsage doesn't have usage_number, removed code gen
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Subscription Usage record created successfully.')
        return super().form_valid(form)

