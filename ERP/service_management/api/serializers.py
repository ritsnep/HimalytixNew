# service_management/api/serializers.py
"""
REST API Serializers for Service Management features
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
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
            'is_active'
        ]
        read_only_fields = ['organization']


class DeviceModelSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = DeviceModel
        fields = [
            'id', 'organization', 'model_number', 'model_name',
            'category', 'category_name', 'manufacturer', 'description',
            'standard_warranty_months', 'cost_price', 'sale_price',
            'is_active', 'specifications',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']


class DeviceStateHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceStateHistory
        fields = [
            'id', 'device', 'from_state', 'to_state',
            'changed_by', 'change_date'
        ]
        read_only_fields = ['change_date']


class DeviceLifecycleSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='device_model.model_name', read_only=True)
    is_warranty_active = serializers.BooleanField(source='is_under_warranty', read_only=True)
    state_history_list = DeviceStateHistorySerializer(source='state_history', many=True, read_only=True)
    
    class Meta:
        model = DeviceLifecycle
        fields = [
            'id', 'organization', 'serial_number', 'asset_tag', 'device_model', 'model_name',
            'customer_id', 'state', 'state_changed_at', 'deployed_date', 'deployment_location',
            'service_contract', 'warranty_start_date', 'warranty_end_date',
            'extended_warranty', 'is_warranty_active', 'last_telemetry_received',
            'telemetry_status', 'firmware_version', 'notes', 'metadata',
            'state_history_list', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'is_warranty_active', 'created_at', 'updated_at'
        ]


class ServiceContractSerializer(serializers.ModelSerializer):
    is_currently_active = serializers.BooleanField(source='is_active', read_only=True)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceContract
        fields = [
            'id', 'organization', 'contract_number', 'customer_id',
            'contract_type', 'status', 'start_date', 'end_date',
            'renewal_date', 'auto_renew', 'annual_value', 'billing_frequency',
            'response_time_hours', 'resolution_time_hours',
            'uptime_guarantee_percent', 'is_currently_active', 'days_remaining',
            'terms', 'notes', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'contract_number', 'is_currently_active',
            'days_remaining', 'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_days_remaining(self, obj) -> int | None:
        if obj.end_date and obj.is_active():
            from django.utils import timezone
            delta = obj.end_date - timezone.now().date()
            return delta.days
        return None


class ServiceTicketSerializer(serializers.ModelSerializer):
    contract_number = serializers.CharField(source='service_contract.contract_number', read_only=True, allow_null=True)
    device_serial = serializers.CharField(source='device.serial_number', read_only=True, allow_null=True)
    is_sla_breached = serializers.BooleanField(source='sla_breach', read_only=True)
    resolution_time_hours = serializers.SerializerMethodField()
    
    class Meta:
        model = ServiceTicket
        fields = [
            'id', 'organization', 'ticket_number', 'service_contract',
            'contract_number', 'customer_id', 'device', 'device_serial',
            'subject', 'description', 'priority', 'status',
            'assigned_to', 'assigned_date', 'created_date',
            'first_response_date', 'resolution_date', 'closed_date',
            'sla_breach', 'is_sla_breached', 'resolution_time_hours',
            'resolution_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'ticket_number', 'is_sla_breached',
            'resolution_time_hours', 'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_resolution_time_hours(self, obj) -> float | None:
        if obj.resolution_date:
            delta = obj.resolution_date - obj.created_date
            return delta.total_seconds() / 3600
        return None


class WarrantyPoolSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='device_model.model_name', read_only=True)
    needs_replenishment_flag = serializers.BooleanField(source='needs_replenishment', read_only=True)
    
    class Meta:
        model = WarrantyPool
        fields = [
            'id', 'organization', 'device_model', 'model_name',
            'pool_name', 'location', 'available_quantity',
            'allocated_quantity', 'minimum_quantity',
            'average_unit_cost', 'needs_replenishment_flag',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'needs_replenishment_flag',
            'created_at', 'updated_at'
        ]


class RMAHardwareSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source='device.serial_number', read_only=True)
    days_in_process = serializers.SerializerMethodField()
    
    class Meta:
        model = RMAHardware
        fields = [
            'id', 'organization', 'rma_number', 'device', 'device_serial',
            'service_contract', 'service_ticket', 'customer_id',
            'status', 'failure_type', 'failure_description',
            'requested_date', 'approved_date', 'received_date',
            'completed_date', 'is_under_warranty', 'warranty_claim_number',
            'replacement_device', 'replacement_shipped_date',
            'repair_action', 'repair_cost', 'return_tracking_number',
            'replacement_tracking_number', 'resolution_notes',
            'days_in_process', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'organization', 'rma_number', 'days_in_process',
            'created_at', 'updated_at'
        ]
    
    @extend_schema_field(serializers.IntegerField())
    def get_days_in_process(self, obj) -> int:
        from django.utils import timezone
        end_date = obj.completed_date if obj.completed_date else timezone.now()
        delta = end_date - obj.requested_date
        return delta.days


class DeviceProvisioningTemplateSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='device_model.model_name', read_only=True, allow_null=True)
    
    class Meta:
        model = DeviceProvisioningTemplate
        fields = [
            'id', 'organization', 'template_name', 'device_model',
            'model_name', 'configuration_script', 'firmware_url',
            'required_firmware_version', 'provisioning_metadata',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['organization', 'created_at', 'updated_at']


class DeviceProvisioningLogSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source='device.serial_number', read_only=True)
    template_name = serializers.CharField(source='template.template_name', read_only=True, allow_null=True)
    
    class Meta:
        model = DeviceProvisioningLog
        fields = [
            'id', 'device', 'device_serial',
            'template', 'template_name', 'provisioning_date',
            'provisioned_by', 'status', 'firmware_version_applied',
            'configuration_applied', 'error_log', 'completion_date'
        ]
        read_only_fields = ['provisioning_date', 'completion_date']
