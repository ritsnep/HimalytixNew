# service_management/views/__init__.py
"""Import all views for easier access"""
from .base_views import BaseListView
from .views_list import (
    ServiceTicketListView, ServiceContractListView, DeviceLifecycleListView,
    WarrantyPoolListView, RMAHardwareListView
)
from .views_create import (
    ServiceTicketCreateView, ServiceContractCreateView, DeviceLifecycleCreateView,
    WarrantyPoolCreateView, RMAHardwareCreateView
)
from .views_update import (
    ServiceTicketUpdateView, ServiceContractUpdateView, DeviceLifecycleUpdateView,
    WarrantyPoolUpdateView, RMAHardwareUpdateView
)

__all__ = [
    'BaseListView',
    'ServiceTicketListView', 'ServiceContractListView', 'DeviceLifecycleListView',
    'WarrantyPoolListView', 'RMAHardwareListView',
    'ServiceTicketCreateView', 'ServiceContractCreateView', 'DeviceLifecycleCreateView',
    'WarrantyPoolCreateView', 'RMAHardwareCreateView',
    'ServiceTicketUpdateView', 'ServiceContractUpdateView', 'DeviceLifecycleUpdateView',
    'WarrantyPoolUpdateView', 'RMAHardwareUpdateView',
]
