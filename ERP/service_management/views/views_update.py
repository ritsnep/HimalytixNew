# service_management/views/views_update.py
"""Update views for service_management models"""
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from usermanagement.mixins import UserOrganizationMixin
from ..forms import (
    ServiceTicketForm, ServiceContractForm, DeviceLifecycleForm,
    WarrantyPoolForm, RMAHardwareForm
)
from ..models import ServiceTicket, ServiceContract, DeviceLifecycle, WarrantyPool, RMAHardware


class ServiceTicketUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = ServiceTicket
    form_class = ServiceTicketForm
    template_name = 'service_management/serviceticket_form.html'
    permission_required = 'service_management.change_serviceticket'
    success_url = reverse_lazy('service:serviceticket_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Service Ticket "{form.instance.ticket_number}" updated successfully.')
        return super().form_valid(form)


class ServiceContractUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = ServiceContract
    form_class = ServiceContractForm
    template_name = 'service_management/servicecontract_form.html'
    permission_required = 'service_management.change_servicecontract'
    success_url = reverse_lazy('service:servicecontract_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Service Contract "{form.instance.contract_number}" updated successfully.')
        return super().form_valid(form)


class DeviceLifecycleUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = DeviceLifecycle
    form_class = DeviceLifecycleForm
    template_name = 'service_management/devicelifecycle_form.html'
    permission_required = 'service_management.change_devicelifecycle'
    success_url = reverse_lazy('service:devicelifecycle_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Device "{form.instance.device_number}" updated successfully.')
        return super().form_valid(form)


class WarrantyPoolUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = WarrantyPool
    form_class = WarrantyPoolForm
    template_name = 'service_management/warrantypool_form.html'
    permission_required = 'service_management.change_warrantypool'
    success_url = reverse_lazy('service_management:warrantypool_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Warranty Pool "{form.instance.pool_name}" updated successfully.')
        return super().form_valid(form)


class RMAHardwareUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = RMAHardware
    form_class = RMAHardwareForm
    template_name = 'service_management/rmahardware_form.html'
    permission_required = 'service_management.change_rmahardware'
    success_url = reverse_lazy('service:rmahardware_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Hardware RMA "{form.instance.rma_number}" updated successfully.')
        return super().form_valid(form)

