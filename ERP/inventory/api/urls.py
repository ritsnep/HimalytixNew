# Inventory/api/urls.py
"""
URL routing for Inventory API endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ProductCategoryViewSet, ProductViewSet, WarehouseViewSet,
    LocationViewSet, BatchViewSet, InventoryItemViewSet,
    StockLedgerViewSet, PriceListViewSet, PriceListItemViewSet,
    CustomerPriceListViewSet, PromotionRuleViewSet,
    TransitWarehouseViewSet, PickListViewSet, PackingSlipViewSet,
    ShipmentViewSet, BackorderViewSet, RMAViewSet,
    calculate_atp, allocate_inventory, check_order_availability,
    get_fulfillment_options
)
from .import_export_views import (
    import_products, import_price_list, import_inventory_adjustment, import_bom,
    export_product_template, export_products, export_price_list_template,
    export_price_list, export_inventory_count_template, export_stock_report,
    export_bom_template, export_bom
)

router = DefaultRouter()

# Product & Inventory
router.register(r'categories', ProductCategoryViewSet, basename='inventory-category')
router.register(r'products', ProductViewSet, basename='inventory-product')
router.register(r'warehouses', WarehouseViewSet, basename='inventory-warehouse')
router.register(r'locations', LocationViewSet, basename='inventory-location')
router.register(r'batches', BatchViewSet, basename='inventory-batch')
router.register(r'inventory-items', InventoryItemViewSet, basename='inventory-item')
router.register(r'stock-ledger', StockLedgerViewSet, basename='stock-ledger')

# Pricing
router.register(r'price-lists', PriceListViewSet, basename='price-list')
router.register(r'price-list-items', PriceListItemViewSet, basename='price-list-item')
router.register(r'customer-price-lists', CustomerPriceListViewSet, basename='customer-price-list')
router.register(r'promotions', PromotionRuleViewSet, basename='promotion')

# Fulfillment
router.register(r'transit-warehouses', TransitWarehouseViewSet, basename='transit-warehouse')
router.register(r'pick-lists', PickListViewSet, basename='pick-list')
router.register(r'packing-slips', PackingSlipViewSet, basename='packing-slip')
router.register(r'shipments', ShipmentViewSet, basename='shipment')
router.register(r'backorders', BackorderViewSet, basename='backorder')
router.register(r'rmas', RMAViewSet, basename='rma')

urlpatterns = [
    path('', include(router.urls)),
    
    # Import endpoints
    path('import/products/', import_products, name='import-products'),
    path('import/price-list/', import_price_list, name='import-price-list'),
    path('import/adjustments/', import_inventory_adjustment, name='import-adjustments'),
    path('import/bom/', import_bom, name='import-bom'),
    
    # Export endpoints
    path('export/product-template/', export_product_template, name='export-product-template'),
    path('export/products/', export_products, name='export-products'),
    path('export/price-list-template/', export_price_list_template, name='export-price-list-template'),
    path('export/price-list/<int:price_list_id>/', export_price_list, name='export-price-list'),
    path('export/count-template/', export_inventory_count_template, name='export-count-template'),
    path('export/stock-report/', export_stock_report, name='export-stock-report'),
    path('export/bom-template/', export_bom_template, name='export-bom-template'),
    path('export/bom/<int:bom_id>/', export_bom, name='export-bom'),
    
    # Allocation endpoints
    path('allocation/atp/', calculate_atp, name='calculate-atp'),
    path('allocation/allocate/', allocate_inventory, name='allocate-inventory'),
    path('allocation/check-availability/', check_order_availability, name='check-availability'),
    path('allocation/fulfillment-options/', get_fulfillment_options, name='fulfillment-options'),
]
