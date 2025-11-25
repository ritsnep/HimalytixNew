from django.urls import include, path
from rest_framework.routers import DefaultRouter

from lpg_vertical import views

app_name = "lpg_vertical"

router = DefaultRouter()
router.register(r"cylinder-types", views.CylinderTypeViewSet, basename="cylinder-type")
router.register(r"cylinder-skus", views.CylinderSKUViewSet, basename="cylinder-sku")
router.register(r"conversion-rules", views.ConversionRuleViewSet, basename="conversion-rule")
router.register(r"dealers", views.DealerViewSet, basename="dealer")
router.register(r"products", views.LpgProductViewSet, basename="lpg-product")
router.register(r"transport-providers", views.TransportProviderViewSet, basename="transport-provider")
router.register(r"vehicles", views.VehicleViewSet, basename="vehicle")
router.register(r"noc-purchases", views.NocPurchaseViewSet, basename="noc-purchase")
router.register(r"sales-invoices", views.SalesInvoiceViewSet, basename="sales-invoice")
router.register(r"logistics-trips", views.LogisticsTripViewSet, basename="logistics-trip")
router.register(r"inventory-movements", views.InventoryMovementViewSet, basename="inventory-movement")

urlpatterns = [
    path("spa/", views.LpgSpaView.as_view(), name="spa"),
    path("spa/masters/", views.spa_masters, name="spa_masters"),
    path("spa/noc/", views.spa_noc, name="spa_noc"),
    path("spa/sales/", views.spa_sales, name="spa_sales"),
    path("spa/logistics/", views.spa_logistics, name="spa_logistics"),
    path("spa/dashboard/", views.spa_dashboard, name="spa_dashboard"),
    path("dashboard/summary/", views.dashboard_summary_view, name="dashboard_summary"),
    path("dashboard/revenue-expense-trend/", views.revenue_expense_trend_view, name="revenue_expense_trend"),
    path("reports/profit-loss/", views.profit_and_loss_view, name="profit_loss"),
    path("", include(router.urls)),
]
