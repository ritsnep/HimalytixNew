# Inventory/views/__init__.py
"""
Import all views for easier access
"""
from .base_views import BaseListView
from .views_list import (
    ProductCategoryListView, ProductListView, WarehouseListView, LocationListView,
    PriceListListView, PickListListView, ShipmentListView, RMAListView,
    BillOfMaterialListView
)
from .views_create import (
    ProductCategoryCreateView, ProductCreateView, WarehouseCreateView, LocationCreateView,
    PriceListCreateView, PickListCreateView, ShipmentCreateView, RMACreateView,
    BillOfMaterialCreateView
)
from .views_update import (
    ProductCategoryUpdateView, ProductUpdateView, WarehouseUpdateView, LocationUpdateView,
    PriceListUpdateView, PickListUpdateView, ShipmentUpdateView, RMAUpdateView,
    BillOfMaterialUpdateView
)
from .views_detail import (
    ProductCategoryDetailView, ProductDetailView, WarehouseDetailView, LocationDetailView,
    PriceListDetailView, PickListDetailView, ShipmentDetailView, RMADetailView,
    BillOfMaterialDetailView
)
from .reports import stock_report, ledger_report

__all__ = [
    'BaseListView',
    # List views
    'ProductCategoryListView', 'ProductListView', 'WarehouseListView', 'LocationListView',
    'PriceListListView', 'PickListListView', 'ShipmentListView', 'RMAListView',
    'BillOfMaterialListView',
    # Create views
    'ProductCategoryCreateView', 'ProductCreateView', 'WarehouseCreateView', 'LocationCreateView',
    'PriceListCreateView', 'PickListCreateView', 'ShipmentCreateView', 'RMACreateView',
    'BillOfMaterialCreateView',
    # Update views
    'ProductCategoryUpdateView', 'ProductUpdateView', 'WarehouseUpdateView', 'LocationUpdateView',
    'PriceListUpdateView', 'PickListUpdateView', 'ShipmentUpdateView', 'RMAUpdateView',
    'BillOfMaterialUpdateView',
    # Detail views
    'ProductCategoryDetailView', 'ProductDetailView', 'WarehouseDetailView', 'LocationDetailView',
    'PriceListDetailView', 'PickListDetailView', 'ShipmentDetailView', 'RMADetailView',
    'BillOfMaterialDetailView',
    # Report views
    'stock_report', 'ledger_report',
]
