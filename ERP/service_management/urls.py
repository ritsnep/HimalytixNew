# service_management/urls.py
from django.urls import path
from .views import (
    ServiceTicketListView, ServiceTicketCreateView, ServiceTicketUpdateView,
    ServiceContractListView, ServiceContractCreateView, ServiceContractUpdateView,
    DeviceLifecycleListView, DeviceLifecycleCreateView, DeviceLifecycleUpdateView,
    WarrantyPoolListView, WarrantyPoolCreateView, WarrantyPoolUpdateView,
    RMAHardwareListView, RMAHardwareCreateView, RMAHardwareUpdateView,
)

app_name = 'service_management'

urlpatterns = [
    # Service Ticket URLs
    path('tickets/', ServiceTicketListView.as_view(), name='serviceticket_list'),
    path('tickets/create/', ServiceTicketCreateView.as_view(), name='serviceticket_create'),
    path('tickets/<int:pk>/edit/', ServiceTicketUpdateView.as_view(), name='serviceticket_update'),
    
    # Service Contract URLs
    path('contracts/', ServiceContractListView.as_view(), name='servicecontract_list'),
    path('contracts/create/', ServiceContractCreateView.as_view(), name='servicecontract_create'),
    path('contracts/<int:pk>/edit/', ServiceContractUpdateView.as_view(), name='servicecontract_update'),
    
    # Device Lifecycle URLs
    path('devices/', DeviceLifecycleListView.as_view(), name='devicelifecycle_list'),
    path('devices/create/', DeviceLifecycleCreateView.as_view(), name='devicelifecycle_create'),
    path('devices/<int:pk>/edit/', DeviceLifecycleUpdateView.as_view(), name='devicelifecycle_update'),
    
    # Warranty Pool URLs
    path('warranties/', WarrantyPoolListView.as_view(), name='warrantypool_list'),
    path('warranties/create/', WarrantyPoolCreateView.as_view(), name='warrantypool_create'),
    path('warranties/<int:pk>/edit/', WarrantyPoolUpdateView.as_view(), name='warrantypool_update'),
    
    # RMA Hardware URLs
    path('rmas/', RMAHardwareListView.as_view(), name='rmahardware_list'),
    path('rmas/create/', RMAHardwareCreateView.as_view(), name='rmahardware_create'),
    path('rmas/<int:pk>/edit/', RMAHardwareUpdateView.as_view(), name='rmahardware_update'),
]
