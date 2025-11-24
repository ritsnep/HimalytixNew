# service_management/admin.py
from django.contrib import admin
from .models import (
    DeviceCategory, DeviceModel, DeviceLifecycle, DeviceStateHistory,
    ServiceContract, ServiceTicket, WarrantyPool, RMAHardware,
    DeviceProvisioningTemplate, DeviceProvisioningLog
)

@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'organization', 'is_active')
    list_filter = ('organization', 'is_active')
    search_fields = ('code', 'name')

@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ('model_number', 'manufacturer', 'model_name', 'category', 'is_active')
    list_filter = ('manufacturer', 'category', 'is_active')
    search_fields = ('model_number', 'model_name', 'manufacturer')

@admin.register(DeviceLifecycle)
class DeviceLifecycleAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'device_model', 'state', 'customer_id', 'deployed_date')
    list_filter = ('state', 'organization')
    search_fields = ('serial_number', 'asset_tag')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ServiceContract)
class ServiceContractAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'customer_id', 'contract_type', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'contract_type', 'auto_renew')
    search_fields = ('contract_number',)

@admin.register(ServiceTicket)
class ServiceTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'subject', 'priority', 'status', 'created_date')
    list_filter = ('priority', 'status', 'sla_breach')
    search_fields = ('ticket_number', 'subject')

@admin.register(RMAHardware)
class RMAHardwareAdmin(admin.ModelAdmin):
    list_display = ('rma_number', 'device', 'status', 'failure_type', 'requested_date')
    list_filter = ('status', 'failure_type', 'is_under_warranty')
    search_fields = ('rma_number', 'device__serial_number')

admin.site.register(DeviceStateHistory)
admin.site.register(WarrantyPool)
admin.site.register(DeviceProvisioningTemplate)
admin.site.register(DeviceProvisioningLog)
