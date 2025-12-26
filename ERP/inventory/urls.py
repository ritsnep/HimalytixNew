from inventory.views import VendorPriceHistoryListView, CustomerPriceHistoryListView
from django.urls import path
from inventory import views as views_module
from inventory.views import (
    ProductCategoryListView, ProductCategoryCreateView, ProductCategoryUpdateView, ProductCategoryDetailView, ProductCategoryDeleteView,
    ProductListView, ProductCreateView, ProductUpdateView, ProductDetailView, ProductDeleteView,
    WarehouseListView, WarehouseCreateView, WarehouseUpdateView, WarehouseDetailView, WarehouseDeleteView,
    LocationListView, LocationCreateView, LocationUpdateView, LocationDetailView, LocationDeleteView,
    UnitListView, UnitCreateView, UnitUpdateView,
    ProductUnitListView, ProductUnitCreateView, ProductUnitUpdateView,
    PriceListListView, PriceListCreateView, PriceListUpdateView, PriceListDetailView, PriceListDeleteView,
    PickListListView, PickListCreateView, PickListUpdateView, PickListDetailView, PickListDeleteView,
    ShipmentListView, ShipmentCreateView, ShipmentUpdateView, ShipmentDetailView, ShipmentDeleteView,
    RMAListView, RMACreateView, RMAUpdateView, RMADetailView, RMADeleteView,
    BillOfMaterialListView, BillOfMaterialCreateView, BillOfMaterialUpdateView, BillOfMaterialDetailView, BillOfMaterialDeleteView,
    TransferOrderListView, TransferOrderCreateView, TransferOrderDetailView, TransferOrderExportView,
    ReorderRecommendationListView, barcode_scanner, scan_barcode,
)

app_name = 'inventory'

urlpatterns = [
        # Price History URLs
        path('vendor-price-history/', VendorPriceHistoryListView.as_view(), name='vendor_price_history_list'),
        path('customer-price-history/', CustomerPriceHistoryListView.as_view(), name='customer_price_history_list'),
    # Inventory Dashboard
    path('', views_module.inventory_dashboard, name='dashboard'),
    path('overview/products/', views_module.products, name='products'),
    path('overview/categories/', views_module.categories, name='categories'),
    path('overview/warehouses/', views_module.warehouses, name='warehouses'),
    path('stock-movements/', views_module.stock_movements, name='stock_movements'),
    path('stock-ledger/<int:pk>/reverse/', views_module.stock_ledger_reverse, name='stock_ledger_reverse'),
    path('stock/receipts/new/', views_module.stock_receipt_create, name='stock_receipt_create'),
    path('stock/issues/new/', views_module.stock_issue_create, name='stock_issue_create'),
    path('stock/adjustments/new/', views_module.stock_adjustment_create, name='stock_adjustment_create'),
    
    # Stock Reports
    path('stock/', views_module.stock_report, name='stock_report'),
    path('ledger/', views_module.ledger_report, name='ledger_report'),
    
    # Legacy function-based views - commented out until implemented
    # path('dashboard/', views.dashboard, name='dashboard'),
    # path('stock-movements/', views.stock_movements, name='stock_movements'),
    # path('stock-receipts/new/', views.stock_receipt_create, name='stock_receipt_create'),
    # path('stock-issues/new/', views.stock_issue_create, name='stock_issue_create'),
    
    # Product Category URLs
    path('categories/', ProductCategoryListView.as_view(), name='product_category_list'),
    path('categories/create/', ProductCategoryCreateView.as_view(), name='product_category_create'),
    path('categories/<int:pk>/', ProductCategoryDetailView.as_view(), name='product_category_detail'),
    path('categories/<int:pk>/edit/', ProductCategoryUpdateView.as_view(), name='product_category_update'),
    path('categories/<int:pk>/delete/', ProductCategoryDeleteView.as_view(), name='product_category_delete'),
    
    # Product URLs
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    
    # Warehouse URLs
    path('warehouses/', WarehouseListView.as_view(), name='warehouse_list'),
    path('warehouses/create/', WarehouseCreateView.as_view(), name='warehouse_create'),
    path('warehouses/<int:pk>/', WarehouseDetailView.as_view(), name='warehouse_detail'),
    path('warehouses/<int:pk>/edit/', WarehouseUpdateView.as_view(), name='warehouse_update'),
    path('warehouses/<int:pk>/delete/', WarehouseDeleteView.as_view(), name='warehouse_delete'),
    
    # Location URLs
    path('locations/', LocationListView.as_view(), name='location_list'),
    path('locations/create/', LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/', LocationDetailView.as_view(), name='location_detail'),
    path('locations/<int:pk>/edit/', LocationUpdateView.as_view(), name='location_update'),
    path('locations/<int:pk>/delete/', LocationDeleteView.as_view(), name='location_delete'),
    
    # Unit URLs
    path('units/', UnitListView.as_view(), name='unit_list'),
    path('units/create/', UnitCreateView.as_view(), name='unit_create'),
    path('units/<int:pk>/edit/', UnitUpdateView.as_view(), name='unit_update'),
    
    # Product Unit URLs
    path('productunits/', ProductUnitListView.as_view(), name='productunit_list'),
    path('productunits/create/', ProductUnitCreateView.as_view(), name='productunit_create'),
    path('productunits/<int:pk>/edit/', ProductUnitUpdateView.as_view(), name='productunit_update'),
    
    # Price List URLs
    path('pricelists/', PriceListListView.as_view(), name='pricelist_list'),
    path('pricelists/create/', PriceListCreateView.as_view(), name='pricelist_create'),
    path('pricelists/<int:pk>/', PriceListDetailView.as_view(), name='pricelist_detail'),
    path('pricelists/<int:pk>/edit/', PriceListUpdateView.as_view(), name='pricelist_update'),
    path('pricelists/<int:pk>/delete/', PriceListDeleteView.as_view(), name='pricelist_delete'),
    
    # Pick List URLs
    path('picklists/', PickListListView.as_view(), name='picklist_list'),
    path('picklists/create/', PickListCreateView.as_view(), name='picklist_create'),
    path('picklists/<int:pk>/', PickListDetailView.as_view(), name='picklist_detail'),
    path('picklists/<int:pk>/edit/', PickListUpdateView.as_view(), name='picklist_update'),
    path('picklists/<int:pk>/delete/', PickListDeleteView.as_view(), name='picklist_delete'),
    
    # Shipment URLs
    path('shipments/', ShipmentListView.as_view(), name='shipment_list'),
    path('shipments/create/', ShipmentCreateView.as_view(), name='shipment_create'),
    path('shipments/<int:pk>/', ShipmentDetailView.as_view(), name='shipment_detail'),
    path('shipments/<int:pk>/edit/', ShipmentUpdateView.as_view(), name='shipment_update'),
    path('shipments/<int:pk>/delete/', ShipmentDeleteView.as_view(), name='shipment_delete'),
    
    # RMA URLs
    path('rmas/', RMAListView.as_view(), name='rma_list'),
    path('rmas/create/', RMACreateView.as_view(), name='rma_create'),
    path('rmas/<int:pk>/', RMADetailView.as_view(), name='rma_detail'),
    path('rmas/<int:pk>/edit/', RMAUpdateView.as_view(), name='rma_update'),
    path('rmas/<int:pk>/delete/', RMADeleteView.as_view(), name='rma_delete'),
    
    # Bill of Material URLs
    path('boms/', BillOfMaterialListView.as_view(), name='bom_list'),
    path('boms/create/', BillOfMaterialCreateView.as_view(), name='bom_create'),
    path('boms/<int:pk>/', BillOfMaterialDetailView.as_view(), name='bom_detail'),
    path('boms/<int:pk>/edit/', BillOfMaterialUpdateView.as_view(), name='bom_update'),
    path('boms/<int:pk>/delete/', BillOfMaterialDeleteView.as_view(), name='bom_delete'),

    # Transfer Order URLs
    path('transfers/', TransferOrderListView.as_view(), name='transfer_order_list'),
    path('transfers/create/', TransferOrderCreateView.as_view(), name='transfer_order_create'),
    path('transfers/<int:pk>/', TransferOrderDetailView.as_view(), name='transfer_order_detail'),
    path('transfers/export/', TransferOrderExportView.as_view(), name='transfer_order_export'),
    path('reorder-recommendations/', ReorderRecommendationListView.as_view(), name='reorder_recommendation_list'),
    path('barcode-scanner/', barcode_scanner, name='barcode_scanner'),
    path('barcode-scan/', scan_barcode, name='scan_barcode'),
]
