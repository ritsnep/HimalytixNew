# service_management/api/serializers.py
"""
REST API Serializers for Service Management features
"""
from rest_framework import serializers
from ..models import (
    DeviceCategory, DeviceModel, DeviceLifecycle, DeviceStateHistory,
    ServiceContract, ServiceTicket, WarrantyPool, RMAHardware,
    DeviceProvisioningTemplate, DeviceProvisioningLog
)


class DeviceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceCategory
        fields = [
            'id', 'organization', 'code', 'name', 'description',
            'parent', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']


class DeviceModelSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = DeviceModel
        fields = [
            'id', 'organization', 'model_number', 'model_name',
            'category', 'category_name', 'manufacturer', 'description',
            'default_warranty_months', 'average_lifespan_months',
            'standard_cost', 'is_active', 'specifications', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']


class DeviceStateHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceStateHistory
        fields = [
            'id', 'from_state', 'to_state', 'changed_at',
            'changed_by', 'reason', 'metadata'
        ]
        read_only_fields = ['changed_at']


class DeviceLifecycleSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.model_name', read_only=True)
    is_warranty_active = serializers.BooleanField(source='is_under_warranty', read_only=True)
    state_history = DeviceStateHistorySerializer(many=True, read_only=True)
    age_months = serializers.SerializerMethodField()
    
    class Meta:
        model = DeviceLifecycle
        fields = [
            'id', 'organization', 'device_serial', 'model', 'model_name',
            'customer_id', 'current_state', 'purchase_date', 'activation_date',
            'warranty_start', 'warranty_end', 'is_warranty_active',
            'deployed_date', 'retired_date', 'location', 'assigned_to',
            'firmware_version', 'last_maintenance_date', 'notes',
            'age_months', 'state_history', 'metadata',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'organization', 'is_warranty_active', 'age_months',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_age_months(self, obj):
        if obj.purchase_date:
            from django.utils import timezone
            delta = timezone.now().date() - obj.purchase_date
            return delta.days // 30
        return None


class ServiceContractSerializer(serializers.ModelSerializer):
    is_currently_active = serializers.BooleanField(source='is_active', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceContract
        fields = [
            'id', 'organization', 'contract_number', 'customer_id',
            'contract_type', 'start_date', 'end_date', 'billing_frequency',
            'contract_value', 'currency_code', 'sla_response_hours',
            'sla_resolution_hours', 'support_hours', 'is_auto_renew',
            'renewal_notice_days', 'is_currently_active', 'days_remaining',
            'notes', 'metadata', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'organization', 'contract_number', 'is_currently_active',
            'days_remaining', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def get_days_remaining(self, obj):
        if obj.end_date and obj.is_active():
            from django.utils import timezone
            delta = obj.end_date - timezone.now().date()
            return delta.days
        return None


class ServiceTicketSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source='service_contract.contract_number', read_only=True)
    device_serial = serializers.CharField(source='device.device_serial', read_only=True)
    is_sla_breached = serializers.SerializerMethodField()
    resolution_time_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceTicket
        fields = [
            'id', 'organization', 'ticket_number', 'service_contract',
            'contract_number', 'customer_id', 'device', 'device_serial',
            'priority', 'status', 'issue_type', 'subject', 'description',
            'reported_date', 'acknowledged_date', 'assigned_to',
            'resolved_date', 'closed_date', 'sla_response_due',
            'sla_resolution_due', 'is_sla_breached', 'resolution_time_hours',
            'resolution_notes', 'root_cause', 'parts_used', 'labor_hours',
            'metadata', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'organization', 'ticket_number', 'sla_response_due',
            'sla_resolution_due', 'is_sla_breached', 'resolution_time_hours',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_is_sla_breached(self, obj):
        from django.utils import timezone
        now = timezone.now()
        
        if obj.status not in ['open', 'in_progress']:
            return False
        
        if obj.sla_resolution_due and now > obj.sla_resolution_due:
            return True
        
        return False
    
    def get_resolution_time_hours(self, obj):
        if obj.resolved_date:
            delta = obj.resolved_date - obj.reported_date
            return delta.total_seconds() / 3600
        return None


class WarrantyPoolSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='device_model.model_name', read_only=True)
    utilization_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = WarrantyPool
        fields = [
            'id', 'organization', 'pool_number', 'device_model',
            'model_name', 'total_devices', 'warranty_start_date',
            'warranty_end_date', 'coverage_type', 'max_claims',
            'claims_used', 'utilization_rate', 'provider_name',
            'policy_number', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'pool_number', 'claims_used',
            'utilization_rate', 'created_at', 'updated_at'
        ]
    
    def get_utilization_rate(self, obj):
        if obj.max_claims and obj.max_claims > 0:
            return (obj.claims_used / obj.max_claims) * 100
        return 0


class RMAHardwareSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source='device.device_serial', read_only=True)
    warranty_pool_number = serializers.CharField(source='warranty_pool.pool_number', read_only=True, allow_null=True)
    days_in_process = serializers.SerializerMethodField()
    
    class Meta:
        model = RMAHardware
        fields = [
            'id', 'organization', 'rma_number', 'device', 'device_serial',
            'warranty_pool', 'warranty_pool_number', 'customer_id',
            'reason', 'fault_description', 'status', 'requested_date',
            'approved_date', 'shipped_date', 'received_date',
            'resolved_date', 'replacement_serial', 'repair_cost',
            'is_warranty_claim', 'claim_status', 'days_in_process',
            'notes', 'metadata', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'organization', 'rma_number', 'days_in_process',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_days_in_process(self, obj):
        from django.utils import timezone
        end_date = obj.resolved_date if obj.resolved_date else timezone.now().date()
        delta = end_date - obj.requested_date
        return delta.days


class DeviceProvisioningTemplateSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='device_model.model_name', read_only=True)
    
    class Meta:
        model = DeviceProvisioningTemplate
        fields = [
            'id', 'organization', 'template_name', 'device_model',
            'model_name', 'config_script', 'firmware_version',
            'default_settings', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']


class DeviceProvisioningLogSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source='device.device_serial', read_only=True)
    template_name = serializers.CharField(source='template.template_name', read_only=True, allow_null=True)
    
    class Meta:
        model = DeviceProvisioningLog
        fields = [
            'id', 'organization', 'device', 'device_serial',
            'template', 'template_name', 'provisioned_date',
            'provisioned_by', 'status', 'config_applied',
            'error_log', 'created_at'
        ]
        read_only_fields = ['organization', 'created_at']
