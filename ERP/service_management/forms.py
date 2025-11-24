# service_management/forms.py
"""
Forms for Service Management vertical models
Following the same pattern as accounting forms with BootstrapFormMixin
"""
from django import forms
from .models import (
    ServiceTicket, ServiceContract, DeviceLifecycle,
    WarrantyPool, RMAHardware
)
from accounting.forms_mixin import BootstrapFormMixin


class ServiceTicketForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceTicket
        fields = (
            'ticket_number', 'service_contract', 'device', 'customer_id',
            'subject', 'description', 'priority', 'status',
            'assigned_to', 'resolution_notes'
        )
        widgets = {
            'ticket_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'service_contract': forms.Select(attrs={'class': 'form-select'}),
            'device': forms.Select(attrs={'class': 'form-select'}),
            'customer_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.NumberInput(attrs={'class': 'form-control'}),
            'resolution_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ServiceContractForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceContract
        fields = (
            'contract_number', 'customer_id', 'contract_type', 'status',
            'start_date', 'end_date', 'renewal_date', 'auto_renew',
            'annual_value', 'billing_frequency',
            'response_time_hours', 'resolution_time_hours', 'uptime_guarantee_percent',
            'terms', 'notes'
        )
        widgets = {
            'contract_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'customer_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'renewal_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'annual_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'billing_frequency': forms.TextInput(attrs={'class': 'form-control'}),
            'response_time_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'resolution_time_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'uptime_guarantee_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'terms': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DeviceLifecycleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DeviceLifecycle
        fields = (
            'device_model', 'serial_number', 'asset_tag', 'state',
            'customer_id', 'deployed_date', 'deployment_location',
            'service_contract', 'warranty_start_date', 'warranty_end_date'
        )
        widgets = {
            'device_model': forms.Select(attrs={'class': 'form-select'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'asset_tag': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.Select(attrs={'class': 'form-select'}),
            'customer_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'deployed_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'deployment_location': forms.TextInput(attrs={'class': 'form-control'}),
            'service_contract': forms.Select(attrs={'class': 'form-select'}),
            'warranty_start_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'warranty_end_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
        }


class WarrantyPoolForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WarrantyPool
        fields = (
            'device_model', 'pool_name', 'location',
            'available_quantity', 'allocated_quantity', 'minimum_quantity',
            'average_unit_cost', 'is_active'
        )
        widgets = {
            'device_model': forms.Select(attrs={'class': 'form-select'}),
            'pool_name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'available_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'allocated_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'minimum_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'average_unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RMAHardwareForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RMAHardware
        fields = (
            'rma_number', 'device', 'service_contract', 'service_ticket',
            'customer_id', 'status', 'failure_type', 'failure_description',
            'is_under_warranty', 'warranty_claim_number',
            'replacement_device', 'repair_action', 'repair_cost',
            'return_tracking_number', 'replacement_tracking_number',
            'resolution_notes'
        )
        widgets = {
            'rma_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'device': forms.Select(attrs={'class': 'form-select'}),
            'service_contract': forms.Select(attrs={'class': 'form-select'}),
            'service_ticket': forms.Select(attrs={'class': 'form-select'}),
            'customer_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'failure_type': forms.Select(attrs={'class': 'form-select'}),
            'failure_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_under_warranty': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'warranty_claim_number': forms.TextInput(attrs={'class': 'form-control'}),
            'replacement_device': forms.Select(attrs={'class': 'form-select'}),
            'repair_action': forms.TextInput(attrs={'class': 'form-control'}),
            'repair_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'return_tracking_number': forms.TextInput(attrs={'class': 'form-control'}),
            'replacement_tracking_number': forms.TextInput(attrs={'class': 'form-control'}),
            'resolution_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

