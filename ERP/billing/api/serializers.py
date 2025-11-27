# billing/api/serializers.py
"""
REST API Serializers for Billing/Subscription features
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from ..models import (
    SubscriptionPlan, UsageTier, Subscription, SubscriptionUsage,
    SubscriptionInvoice, DeferredRevenue, DeferredRevenueSchedule,
    MilestoneRevenue
)


class UsageTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageTier
        fields = [
            'id', 'subscription_plan', 'tier_name', 'min_quantity', 'max_quantity',
            'price_per_unit', 'overage_price'
        ]


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    usage_tiers = UsageTierSerializer(many=True, read_only=True)
    is_currently_active = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'organization', 'code', 'name', 'description',
            'plan_type', 'billing_cycle', 'base_price', 'currency_code',
            'trial_period_days', 'setup_fee', 'minimum_commitment_months',
            'auto_renew', 'is_active', 'usage_tiers',
            'is_currently_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_currently_active(self, obj) -> bool:
        return bool(obj.is_active)


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='subscription_plan.name', read_only=True)
    effective_price_value = serializers.DecimalField(
        source='effective_price', max_digits=15, decimal_places=2, read_only=True
    )
    is_currently_active = serializers.SerializerMethodField()
    days_until_renewal = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'organization', 'subscription_number', 'customer_id',
            'subscription_plan', 'plan_name', 'status', 'start_date',
            'trial_end_date', 'current_period_start', 'current_period_end',
            'next_billing_date', 'cancellation_date', 'cancellation_reason',
            'custom_price', 'discount_percent', 'effective_price_value',
            'contract_term_months', 'contract_end_date', 'auto_renew',
            'is_currently_active', 'days_until_renewal', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'subscription_number', 'effective_price_value',
            'is_currently_active', 'days_until_renewal',
            'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.BooleanField())
    def get_is_currently_active(self, obj) -> bool:
        return obj.status == 'active'
    
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_days_until_renewal(self, obj) -> int | None:
        if obj.current_period_end:
            from django.utils import timezone
            delta = obj.current_period_end - timezone.now().date()
            return delta.days
        return None


class SubscriptionUsageSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source='subscription.subscription_number', read_only=True)
    
    class Meta:
        model = SubscriptionUsage
        fields = [
            'id', 'subscription', 'subscription_number', 'usage_date',
            'usage_type', 'quantity', 'unit_of_measure', 'tier_applied',
            'calculated_amount', 'is_billed', 'billed_invoice_id', 'recorded_at'
        ]
        read_only_fields = ['recorded_at']


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source='subscription.subscription_number', read_only=True)
    
    class Meta:
        model = SubscriptionInvoice
        fields = [
            'id', 'organization', 'invoice_id', 'invoice_number', 'subscription',
            'subscription_number', 'billing_period_start', 'billing_period_end',
            'subscription_amount', 'usage_amount', 'setup_fee', 'total_amount',
            'created_at'
        ]
        read_only_fields = [
            'organization', 'invoice_number', 'subscription_number', 'created_at'
        ]


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
    schedule = DeferredRevenueScheduleSerializer(source='schedule_lines', many=True, read_only=True)
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
    
    @extend_schema_field({'type': 'string', 'format': 'decimal'})
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
    
    @extend_schema_field({'type': 'boolean'})
    def get_is_past_due(self, obj):
        if obj.status in ['completed', 'invoiced', 'recognized']:
            return False
        from django.utils import timezone
        return obj.due_date < timezone.now().date()
