from django.urls import path

from rest_framework.routers import DefaultRouter

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

urlpatterns = router.urls

urlpatterns += [
    path('dashboard/metrics/', dashboard_views.dashboard_metrics, name='dashboard_metrics'),
    path('dashboard/export/', dashboard_views.dashboard_export_csv, name='dashboard_export'),
]
