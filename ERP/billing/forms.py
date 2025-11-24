# billing/forms.py
"""
Forms for Billing vertical models
Following the same pattern as accounting forms with BootstrapFormMixin
"""
from django import forms
from .models import (
    SubscriptionPlan, Subscription, SubscriptionInvoice,
    DeferredRevenue, DeferredRevenueSchedule, MilestoneRevenue,
    SubscriptionUsage, UsageTier
)
from accounting.forms_mixin import BootstrapFormMixin


class SubscriptionPlanForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = (
            'code', 'name', 'description', 'plan_type',
            'base_price', 'currency_code', 'trial_period_days',
            'setup_fee', 'is_active'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'plan_type': forms.Select(attrs={'class': 'form-select'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control'}),
            'trial_period_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'setup_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubscriptionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Subscription
        fields = (
            'subscription_number', 'customer_id', 'subscription_plan', 'status',
            'start_date', 'trial_end_date', 'current_period_start', 'current_period_end',
            'next_billing_date', 'custom_price', 'discount_percent',
            'contract_term_months', 'contract_end_date', 'auto_renew'
        )
        widgets = {
            'subscription_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'customer_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'subscription_plan': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'trial_end_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'current_period_start': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'current_period_end': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'next_billing_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'custom_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'contract_term_months': forms.NumberInput(attrs={'class': 'form-control'}),
            'contract_end_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SubscriptionInvoiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SubscriptionInvoice
        fields = (
            'subscription', 'invoice_id', 'invoice_number',
            'billing_period_start', 'billing_period_end',
            'subscription_amount', 'usage_amount', 'setup_fee', 'total_amount'
        )
        widgets = {
            'subscription': forms.Select(attrs={'class': 'form-select'}),
            'invoice_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'invoice_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'billing_period_start': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'billing_period_end': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'subscription_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'usage_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'setup_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class DeferredRevenueForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DeferredRevenue
        fields = (
            'subscription', 'invoice_id', 'contract_value',
            'deferred_amount', 'recognized_amount',
            'service_period_start', 'service_period_end',
            'recognition_method', 'deferred_revenue_account', 'revenue_account'
        )
        widgets = {
            'subscription': forms.Select(attrs={'class': 'form-select'}),
            'invoice_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'contract_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'deferred_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'recognized_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'service_period_start': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'service_period_end': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'recognition_method': forms.Select(attrs={'class': 'form-select'}),
            'deferred_revenue_account': forms.Select(attrs={'class': 'form-select'}),
            'revenue_account': forms.Select(attrs={'class': 'form-select'}),
        }


class DeferredRevenueScheduleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DeferredRevenueSchedule
        fields = (
            'recognition_date', 'recognition_amount', 'is_recognized', 'notes'
        )
        widgets = {
            'recognition_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'recognition_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_recognized': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MilestoneRevenueForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MilestoneRevenue
        fields = (
            'deferred_revenue', 'milestone_number', 'description',
            'deliverable', 'due_date', 'completion_date',
            'status', 'milestone_value', 'recognized_amount', 'notes'
        )
        widgets = {
            'deferred_revenue': forms.Select(attrs={'class': 'form-select'}),
            'milestone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'deliverable': forms.TextInput(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'completion_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'milestone_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'recognized_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MilestoneRevenueForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MilestoneRevenue
        fields = (
            'deferred_revenue', 'milestone_number', 'description',
            'deliverable', 'due_date', 'completion_date',
            'status', 'milestone_value', 'recognized_amount', 'notes'
        )
        widgets = {
            'deferred_revenue': forms.Select(attrs={'class': 'form-select'}),
            'milestone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'deliverable': forms.TextInput(attrs={'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'completion_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'milestone_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'recognized_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class SubscriptionUsageForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SubscriptionUsage
        fields = (
            'subscription', 'usage_date', 'usage_type', 'quantity',
            'unit_of_measure', 'tier_applied', 'calculated_amount',
            'is_billed', 'billed_invoice_id'
        )
        widgets = {
            'subscription': forms.Select(attrs={'class': 'form-select'}),
            'usage_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'usage_type': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'form-control'}),
            'tier_applied': forms.Select(attrs={'class': 'form-select'}),
            'calculated_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_billed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'billed_invoice_id': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class UsageTierForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = UsageTier
        fields = (
            'tier_name', 'min_quantity', 'max_quantity', 'price_per_unit', 'overage_price'
        )
        widgets = {
            'tier_name': forms.TextInput(attrs={'class': 'form-control'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'overage_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


# Inline formsets
DeferredRevenueScheduleFormSet = forms.inlineformset_factory(
    DeferredRevenue, DeferredRevenueSchedule,
    form=DeferredRevenueScheduleForm,
    extra=1,
    can_delete=True
)

UsageTierFormSet = forms.inlineformset_factory(
    SubscriptionPlan, UsageTier,
    form=UsageTierForm,
    extra=1,
    can_delete=True
)
