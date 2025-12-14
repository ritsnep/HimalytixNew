from django.urls import path, include

from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from accounting.api import views, dashboard_views, audit

router = DefaultRouter()
router.register(r'vendors', views.VendorViewSet, basename='vendor')
router.register(r'customers', views.CustomerViewSet, basename='customer')
router.register(r'purchase-invoices', views.PurchaseInvoiceViewSet, basename='purchaseinvoice')
router.register(r'sales-invoices', views.SalesInvoiceViewSet, basename='salesinvoice')
router.register(r'ap-payments', views.APPaymentViewSet, basename='appayment')
router.register(r'ar-receipts', views.ARReceiptViewSet, basename='arreceipt')
router.register(r'bank-accounts', views.BankAccountViewSet, basename='bankaccount')
router.register(r'assets', views.AssetViewSet, basename='asset')
router.register(r'events', views.IntegrationEventViewSet, basename='event')
router.register(r'audit-logs', audit.AuditLogViewSet, basename='auditlog')
router.register(r'journal-lines', views.JournalLineViewSet, basename='journalline')
router.register(r'vouchers', views.VoucherViewSet, basename='voucher')

# Nested router for voucher lines
voucher_router = routers.NestedDefaultRouter(router, r'vouchers', lookup='voucher')
voucher_router.register(r'lines', views.VoucherLineViewSet, basename='voucher-lines')

# Configuration endpoints
router.register(r'voucher-types', views.VoucherTypeViewSet, basename='vouchertype')
router.register(r'configurable-fields', views.ConfigurableFieldViewSet, basename='configurablefield')
router.register(r'field-configs', views.FieldConfigViewSet, basename='fieldconfig')

urlpatterns = router.urls + voucher_router.urls

urlpatterns += [
    path('dashboard/metrics/', dashboard_views.dashboard_metrics, name='dashboard_metrics'),
    path('dashboard/export/', dashboard_views.dashboard_export_csv, name='dashboard_export'),
    path('voucher-config/', views.get_voucher_config, name='get_voucher_config'),
    # Field configuration endpoints
    path('vouchers/types/<int:voucher_type_id>/fields/<str:field_name>/', views.get_field_config, name='get_field_config'),
    path('vouchers/configs/', views.save_field_config, name='save_field_config'),
    path('vouchers/types/<int:voucher_type_id>/reset-defaults/', views.reset_voucher_type_defaults, name='reset_voucher_type_defaults'),
]
