from django.urls import path
from . import views
from .views import (
    ProductCategoryListView, ProductCategoryCreateView, ProductCategoryUpdateView, ProductCategoryDetailView,
    ProductListView, ProductCreateView, ProductUpdateView, ProductDetailView,
    WarehouseListView, WarehouseCreateView, WarehouseUpdateView, WarehouseDetailView,
    LocationListView, LocationCreateView, LocationUpdateView, LocationDetailView,
    PriceListListView, PriceListCreateView, PriceListUpdateView, PriceListDetailView,
    PickListListView, PickListCreateView, PickListUpdateView, PickListDetailView,
    ShipmentListView, ShipmentCreateView, ShipmentUpdateView, ShipmentDetailView,
    RMAListView, RMACreateView, RMAUpdateView, RMADetailView,
    BillOfMaterialListView, BillOfMaterialCreateView, BillOfMaterialUpdateView, BillOfMaterialDetailView,
)

app_name = 'inventory'

urlpatterns = [
    # Stock Reports
    path('stock/', views.stock_report, name='stock_report'),
    path('ledger/', views.ledger_report, name='ledger_report'),
    
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
    
    # Product URLs
    path('products/', ProductListView.as_view(), name='product_list'),
    path('products/create/', ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', ProductUpdateView.as_view(), name='product_update'),
    
    # Warehouse URLs
    path('warehouses/', WarehouseListView.as_view(), name='warehouse_list'),
    path('warehouses/create/', WarehouseCreateView.as_view(), name='warehouse_create'),
    path('warehouses/<int:pk>/', WarehouseDetailView.as_view(), name='warehouse_detail'),
    path('warehouses/<int:pk>/edit/', WarehouseUpdateView.as_view(), name='warehouse_update'),
    
    # Location URLs
    path('locations/', LocationListView.as_view(), name='location_list'),
    path('locations/create/', LocationCreateView.as_view(), name='location_create'),
    path('locations/<int:pk>/', LocationDetailView.as_view(), name='location_detail'),
    path('locations/<int:pk>/edit/', LocationUpdateView.as_view(), name='location_update'),
    
    # Price List URLs
    path('pricelists/', PriceListListView.as_view(), name='pricelist_list'),
    path('pricelists/create/', PriceListCreateView.as_view(), name='pricelist_create'),
    path('pricelists/<int:pk>/', PriceListDetailView.as_view(), name='pricelist_detail'),
    path('pricelists/<int:pk>/edit/', PriceListUpdateView.as_view(), name='pricelist_update'),
    
    # Pick List URLs
    path('picklists/', PickListListView.as_view(), name='picklist_list'),
    path('picklists/create/', PickListCreateView.as_view(), name='picklist_create'),
    path('picklists/<int:pk>/', PickListDetailView.as_view(), name='picklist_detail'),
    path('picklists/<int:pk>/edit/', PickListUpdateView.as_view(), name='picklist_update'),
    
    # Shipment URLs
    path('shipments/', ShipmentListView.as_view(), name='shipment_list'),
    path('shipments/create/', ShipmentCreateView.as_view(), name='shipment_create'),
    path('shipments/<int:pk>/', ShipmentDetailView.as_view(), name='shipment_detail'),
    path('shipments/<int:pk>/edit/', ShipmentUpdateView.as_view(), name='shipment_update'),
    
    # RMA URLs
    path('rmas/', RMAListView.as_view(), name='rma_list'),
    path('rmas/create/', RMACreateView.as_view(), name='rma_create'),
    path('rmas/<int:pk>/', RMADetailView.as_view(), name='rma_detail'),
    path('rmas/<int:pk>/edit/', RMAUpdateView.as_view(), name='rma_update'),
    
    # Bill of Material URLs
    path('boms/', BillOfMaterialListView.as_view(), name='bom_list'),
    path('boms/create/', BillOfMaterialCreateView.as_view(), name='bom_create'),
    path('boms/<int:pk>/', BillOfMaterialDetailView.as_view(), name='bom_detail'),
    path('boms/<int:pk>/edit/', BillOfMaterialUpdateView.as_view(), name='bom_update'),
]
