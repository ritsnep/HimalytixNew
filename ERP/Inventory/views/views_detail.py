# Inventory/views/views_detail.py
"""
Detail views for Inventory models
"""
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import DetailView
from usermanagement.mixins import UserOrganizationMixin
from ..models import (
    ProductCategory, Product, Warehouse, Location,
    PriceList, PickList, Shipment, RMA
)
from enterprise.models import BillOfMaterial


class ProductCategoryDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = ProductCategory
    template_name = 'Inventory/product_category_detail.html'
    permission_required = 'Inventory.view_productcategory'
    context_object_name = 'category'


class ProductDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Product
    template_name = 'Inventory/product_detail.html'
    permission_required = 'Inventory.view_product'
    context_object_name = 'product'


class WarehouseDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Warehouse
    template_name = 'Inventory/warehouse_detail.html'
    permission_required = 'Inventory.view_warehouse'
    context_object_name = 'warehouse'


class LocationDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Location
    template_name = 'Inventory/location_detail.html'
    permission_required = 'Inventory.view_location'
    context_object_name = 'location'


class PriceListDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = PriceList
    template_name = 'Inventory/pricelist_detail.html'
    permission_required = 'Inventory.view_pricelist'
    context_object_name = 'pricelist'


class PickListDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = PickList
    template_name = 'Inventory/picklist_detail.html'
    permission_required = 'Inventory.view_picklist'
    context_object_name = 'picklist'


class ShipmentDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = Shipment
    template_name = 'Inventory/shipment_detail.html'
    permission_required = 'Inventory.view_shipment'
    context_object_name = 'shipment'


class RMADetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = RMA
    template_name = 'Inventory/rma_detail.html'
    permission_required = 'Inventory.view_rma'
    context_object_name = 'rma'


class BillOfMaterialDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = BillOfMaterial
    template_name = 'Inventory/billofmaterial_detail.html'
    permission_required = 'Inventory.view_billofmaterial'
    context_object_name = 'bom'
