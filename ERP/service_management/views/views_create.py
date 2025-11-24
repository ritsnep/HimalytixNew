# service_management/views/views_create.py
"""Create views for service_management models"""
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView
from usermanagement.mixins import UserOrganizationMixin
from accounting.models import AutoIncrementCodeGenerator
from ..forms import (
    ServiceTicketForm, ServiceContractForm, DeviceLifecycleForm,
    WarrantyPoolForm, RMAHardwareForm
)
from ..models import ServiceTicket, ServiceContract, DeviceLifecycle, WarrantyPool, RMAHardware


class ServiceTicketCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = ServiceTicket
    form_class = ServiceTicketForm
    template_name = 'service_management/serviceticket_form.html'
    permission_required = 'service_management.add_serviceticket'
    success_url = reverse_lazy('service:serviceticket_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(ServiceTicket, 'ticket_number', organization=organization, prefix='TKT')
            initial['ticket_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Service Ticket "{form.instance.ticket_number}" created successfully.')
        return super().form_valid(form)


class ServiceContractCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = ServiceContract
    form_class = ServiceContractForm
    template_name = 'service_management/servicecontract_form.html'
    permission_required = 'service_management.add_servicecontract'
    success_url = reverse_lazy('service:servicecontract_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(ServiceContract, 'contract_number', organization=organization, prefix='SCON')
            initial['contract_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Service Contract "{form.instance.contract_number}" created successfully.')
        return super().form_valid(form)


class DeviceLifecycleCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = DeviceLifecycle
    form_class = DeviceLifecycleForm
    template_name = 'service_management/devicelifecycle_form.html'
    permission_required = 'service_management.add_devicelifecycle'
    success_url = reverse_lazy('service:devicelifecycle_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(DeviceLifecycle, 'device_number', organization=organization, prefix='DEV')
            initial['device_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Device "{form.instance.device_number}" created successfully.')
        return super().form_valid(form)


class WarrantyPoolCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = WarrantyPool
    form_class = WarrantyPoolForm
    template_name = 'service_management/warrantypool_form.html'
    permission_required = 'service_management.add_warrantypool'
    success_url = reverse_lazy('service:warrantypool_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(WarrantyPool, 'pool_name', organization=organization, prefix='WP')
            initial['pool_name'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Warranty Pool "{form.instance.pool_name}" created successfully.')
        return super().form_valid(form)


class RMAHardwareCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = RMAHardware
    form_class = RMAHardwareForm
    template_name = 'service_management/rmahardware_form.html'
    permission_required = 'service_management.add_rmahardware'
    success_url = reverse_lazy('service:rmahardware_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(RMAHardware, 'rma_number', organization=organization, prefix='HRMA')
            initial['rma_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Hardware RMA "{form.instance.rma_number}" created successfully.')
        return super().form_valid(form)

