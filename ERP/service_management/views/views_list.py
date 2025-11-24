# service_management/views/views_list.py
"""List views for service management models"""
from django.urls import reverse_lazy
from .base_views import BaseListView
from ..models import ServiceTicket, ServiceContract, DeviceLifecycle, WarrantyPool, RMAHardware


class ServiceTicketListView(BaseListView):
    model = ServiceTicket
    template_name = 'service_management/serviceticket_list.html'
    context_object_name = 'tickets'
    permission_required = ('service_management', 'serviceticket', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('service:serviceticket_create')
        return context


class ServiceContractListView(BaseListView):
    model = ServiceContract
    template_name = 'service_management/servicecontract_list.html'
    context_object_name = 'contracts'
    permission_required = ('service_management', 'servicecontract', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('service:servicecontract_create')
        return context


class DeviceLifecycleListView(BaseListView):
    model = DeviceLifecycle
    template_name = 'service_management/devicelifecycle_list.html'
    context_object_name = 'devices'
    permission_required = ('service_management', 'devicelifecycle', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('service:devicelifecycle_create')
        return context


class WarrantyPoolListView(BaseListView):
    model = WarrantyPool
    template_name = 'service_management/warrantypool_list.html'
    context_object_name = 'warranty_pools'
    permission_required = ('service_management', 'warrantypool', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('service_management:warrantypool_create')
        return context


class RMAHardwareListView(BaseListView):
    model = RMAHardware
    template_name = 'service_management/rmahardware_list.html'
    context_object_name = 'rmas'
    permission_required = ('service_management', 'rmahardware', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('service:rmahardware_create')
        return context



