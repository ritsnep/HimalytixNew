# Inventory/views/views_list.py
"""
List views for Inventory models
"""
from django.urls import reverse_lazy
from .base_views import BaseListView
from ..models import (
    ProductCategory, Product, Warehouse, Location,
    PriceList, PickList, Shipment, RMA
)
from enterprise.models import BillOfMaterial


class ProductCategoryListView(BaseListView):
    model = ProductCategory
    template_name = 'Inventory/product_category_list.html'
    context_object_name = 'categories'
    permission_required = ('Inventory', 'productcategory', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:product_category_create')
        return context


class ProductListView(BaseListView):
    model = Product
    template_name = 'Inventory/product_list.html'
    context_object_name = 'products'
    permission_required = ('Inventory', 'product', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:product_create')
        return context


class WarehouseListView(BaseListView):
    model = Warehouse
    template_name = 'Inventory/warehouse_list.html'
    context_object_name = 'warehouses'
    permission_required = ('Inventory', 'warehouse', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:warehouse_create')
        return context


class LocationListView(BaseListView):
    model = Location
    template_name = 'Inventory/location_list.html'
    context_object_name = 'locations'
    permission_required = ('Inventory', 'location', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:location_create')
        return context


class PriceListListView(BaseListView):
    model = PriceList
    template_name = 'Inventory/pricelist_list.html'
    context_object_name = 'pricelists'
    permission_required = ('Inventory', 'pricelist', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:pricelist_create')
        return context


class PickListListView(BaseListView):
    model = PickList
    template_name = 'Inventory/picklist_list.html'
    context_object_name = 'picklists'
    permission_required = ('Inventory', 'picklist', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:picklist_create')
        return context


class ShipmentListView(BaseListView):
    model = Shipment
    template_name = 'Inventory/shipment_list.html'
    context_object_name = 'shipments'
    permission_required = ('Inventory', 'shipment', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:shipment_create')
        return context


class RMAListView(BaseListView):
    model = RMA
    template_name = 'Inventory/rma_list.html'
    context_object_name = 'rmas'
    permission_required = ('Inventory', 'rma', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:rma_create')
        return context


class BillOfMaterialListView(BaseListView):
    model = BillOfMaterial
    template_name = 'Inventory/billofmaterial_list.html'
    context_object_name = 'boms'
    permission_required = ('Inventory', 'billofmaterial', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse_lazy('inventory:bom_create')
        return context
