# service_management/api/urls.py
"""
URL routing for Service Management API endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeviceCategoryViewSet, DeviceModelViewSet, DeviceLifecycleViewSet,
    DeviceStateHistoryViewSet, ServiceContractViewSet, ServiceTicketViewSet,
    WarrantyPoolViewSet, RMAHardwareViewSet, DeviceProvisioningTemplateViewSet,
    DeviceProvisioningLogViewSet
)

router = DefaultRouter()

router.register(r'device-categories', DeviceCategoryViewSet, basename='device-category')
router.register(r'device-models', DeviceModelViewSet, basename='device-model')
router.register(r'devices', DeviceLifecycleViewSet, basename='device')
router.register(r'device-state-history', DeviceStateHistoryViewSet, basename='device-state-history')
router.register(r'service-contracts', ServiceContractViewSet, basename='service-contract')
router.register(r'service-tickets', ServiceTicketViewSet, basename='service-ticket')
router.register(r'warranty-pools', WarrantyPoolViewSet, basename='warranty-pool')
router.register(r'rma-hardware', RMAHardwareViewSet, basename='rma-hardware')
router.register(r'provisioning-templates', DeviceProvisioningTemplateViewSet, basename='provisioning-template')
router.register(r'provisioning-logs', DeviceProvisioningLogViewSet, basename='provisioning-log')

urlpatterns = [
    path('', include(router.urls)),
]
