# billing/api/serializers.py
"""
REST API Serializers for Billing/Subscription features
"""
from rest_framework import serializers
from ..models import (
    SubscriptionPlan, UsageTier, Subscription, SubscriptionUsage,
    SubscriptionInvoice, DeferredRevenue, DeferredRevenueSchedule,
    MilestoneRevenue
)


class UsageTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageTier
        fields = [
            'id', 'from_quantity', 'to_quantity', 'price_per_unit',
            'flat_fee', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    usage_tiers = UsageTierSerializer(many=True, read_only=True)
    is_currently_active = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'organization', 'code', 'name', 'description',
            'plan_type', 'base_price', 'billing_frequency',
            'billing_frequency_unit', 'trial_period_days',
            'setup_fee', 'is_active', 'currency_code',
            'usage_metric', 'included_usage', 'overage_rate',
            'contract_term_months', 'auto_renew', 'cancellation_notice_days',
            'proration_policy', 'valid_from', 'valid_to',
            'usage_tiers', 'is_currently_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']
    
    def get_is_currently_active(self, obj):
        from django.utils import timezone
        now = timezone.now().date()
        return (obj.is_active and 
                obj.valid_from <= now and 
                (obj.valid_to is None or obj.valid_to >= now))


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    effective_price_value = serializers.DecimalField(
        source='effective_price', max_digits=15, decimal_places=2, read_only=True
    )
    is_currently_active = serializers.BooleanField(source='is_active', read_only=True)
    days_until_renewal = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'organization', 'subscription_number', 'customer_id',
            'plan', 'plan_name', 'status', 'start_date', 'end_date',
            'current_period_start', 'current_period_end', 'trial_end_date',
            'cancellation_date', 'cancellation_reason', 'base_price',
            'discount_percent', 'discount_amount', 'effective_price_value',
            'billing_frequency', 'billing_frequency_unit', 'payment_method',
            'auto_renew', 'contract_term_months', 'renewal_count',
            'is_currently_active', 'days_until_renewal', 'metadata',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'organization', 'subscription_number', 'effective_price_value',
            'is_currently_active', 'days_until_renewal',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_days_until_renewal(self, obj):
        if obj.current_period_end and obj.is_active():
            from django.utils import timezone
            delta = obj.current_period_end - timezone.now().date()
            return delta.days
        return None


class SubscriptionUsageSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source='subscription.subscription_number', read_only=True)
    is_overaged = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionUsage
        fields = [
            'id', 'organization', 'subscription', 'subscription_number',
            'period_start', 'period_end', 'usage_metric', 'quantity_used',
            'included_quantity', 'overage_quantity', 'overage_rate',
            'overage_charge', 'is_billed', 'billing_date',
            'is_overaged', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'overage_quantity', 'overage_charge',
            'is_overaged', 'created_at', 'updated_at'
        ]
    
    def get_is_overaged(self, obj):
        return obj.overage_quantity > 0


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source='subscription.subscription_number', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionInvoice
        fields = [
            'id', 'organization', 'invoice_number', 'subscription',
            'subscription_number', 'invoice_date', 'due_date',
            'period_start', 'period_end', 'base_amount', 'usage_charges',
            'setup_fee', 'prorated_amount', 'discount_amount',
            'tax_amount', 'total_amount', 'currency_code', 'status',
            'payment_date', 'payment_method', 'is_overdue', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'invoice_number', 'is_overdue',
            'created_at', 'updated_at'
        ]
    
    def get_is_overdue(self, obj):
        if obj.status in ['paid', 'cancelled']:
            return False
        from django.utils import timezone
        return obj.due_date < timezone.now().date()


class DeferredRevenueScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeferredRevenueSchedule
        fields = [
            'id', 'recognition_date', 'recognition_amount', 'is_recognized',
            'recognized_date', 'journal_entry_id', 'notes'
        ]
        read_only_fields = ['is_recognized', 'recognized_date', 'journal_entry_id']


class DeferredRevenueSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source='subscription.subscription_number', read_only=True)
    schedule = DeferredRevenueScheduleSerializer(many=True, read_only=True)
    remaining_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = DeferredRevenue
        fields = [
            'id', 'organization', 'subscription', 'subscription_number',
            'invoice_id', 'contract_value', 'deferred_amount',
            'recognized_amount', 'service_period_start',
            'service_period_end', 'recognition_method',
            'deferred_revenue_account',
            'revenue_account', 'is_fully_recognized', 'schedule',
            'remaining_balance', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'recognized_amount', 'is_fully_recognized',
            'remaining_balance', 'created_at', 'updated_at'
        ]
    
    def get_remaining_balance(self, obj):
        return obj.deferred_amount - obj.recognized_amount


class MilestoneRevenueSerializer(serializers.ModelSerializer):
    is_past_due = serializers.SerializerMethodField()
    
    class Meta:
        model = MilestoneRevenue
        fields = [
            'id', 'organization', 'deferred_revenue',
            'milestone_number', 'description', 'deliverable',
            'due_date', 'completion_date', 'status',
            'milestone_value', 'recognized_amount',
            'approved_by', 'approved_date', 'notes',
            'is_past_due', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'milestone_number', 'is_past_due',
            'created_at', 'updated_at'
        ]
    
    def get_is_past_due(self, obj):
        if obj.status in ['completed', 'invoiced', 'recognized']:
            return False
        from django.utils import timezone
        return obj.due_date < timezone.now().date()
