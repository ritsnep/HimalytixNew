# Inventory/views/views_update.py
"""
Update views for Inventory models
"""
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from usermanagement.mixins import UserOrganizationMixin
from ..forms import (
    ProductCategoryForm, ProductForm, WarehouseForm, LocationForm,
    PriceListForm, PickListForm, ShipmentForm, RMAForm, BillOfMaterialForm
)
from ..models import (
    ProductCategory, Product, Warehouse, Location,
    PriceList, PickList, Shipment, RMA
)
from enterprise.models import BillOfMaterial


class ProductCategoryUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = ProductCategory
    form_class = ProductCategoryForm
    template_name = 'Inventory/product_category_form.html'
    permission_required = 'Inventory.change_productcategory'
    success_url = reverse_lazy('inventory:product_category_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Product Category "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class ProductUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'Inventory/product_form.html'
    permission_required = 'Inventory.change_product'
    success_url = reverse_lazy('inventory:product_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Product "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class WarehouseUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'Inventory/warehouse_form.html'
    permission_required = 'Inventory.change_warehouse'
    success_url = reverse_lazy('inventory:warehouse_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Warehouse "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class LocationUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Location
    form_class = LocationForm
    template_name = 'Inventory/location_form.html'
    permission_required = 'Inventory.change_location'
    success_url = reverse_lazy('inventory:location_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Location "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class PriceListUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = PriceList
    form_class = PriceListForm
    template_name = 'Inventory/pricelist_form.html'
    permission_required = 'Inventory.change_pricelist'
    success_url = reverse_lazy('inventory:pricelist_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Price List "{form.instance.name}" updated successfully.')
        return super().form_valid(form)


class PickListUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = PickList
    form_class = PickListForm
    template_name = 'Inventory/picklist_form.html'
    permission_required = 'Inventory.change_picklist'
    success_url = reverse_lazy('inventory:picklist_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Pick List "{form.instance.pick_list_number}" updated successfully.')
        return super().form_valid(form)


class ShipmentUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = Shipment
    form_class = ShipmentForm
    template_name = 'Inventory/shipment_form.html'
    permission_required = 'Inventory.change_shipment'
    success_url = reverse_lazy('inventory:shipment_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Shipment "{form.instance.shipment_number}" updated successfully.')
        return super().form_valid(form)


class RMAUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = RMA
    form_class = RMAForm
    template_name = 'Inventory/rma_form.html'
    permission_required = 'Inventory.change_rma'
    success_url = reverse_lazy('inventory:rma_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'RMA "{form.instance.rma_number}" updated successfully.')
        return super().form_valid(form)


class BillOfMaterialUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'Inventory/billofmaterial_form.html'
    permission_required = 'Inventory.change_billofmaterial'
    success_url = reverse_lazy('inventory:bom_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'BOM "{form.instance.bom_number}" updated successfully.')
        return super().form_valid(form)
