# Inventory/views/views_create.py
"""
Create views for Inventory models
Following the same pattern as accounting/views/views_create.py
"""
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView
from usermanagement.mixins import UserOrganizationMixin
from accounting.models import AutoIncrementCodeGenerator
from ..forms import (
    ProductCategoryForm, ProductForm, WarehouseForm, LocationForm,
    PriceListForm, PickListForm, ShipmentForm, RMAForm, BillOfMaterialForm
)
from ..models import (
    ProductCategory, Product, Warehouse, Location,
    PriceList, PickList, Shipment, RMA
)
from enterprise.models import BillOfMaterial


class ProductCategoryCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = ProductCategory
    form_class = ProductCategoryForm
    template_name = 'Inventory/product_category_form.html'
    permission_required = 'Inventory.add_productcategory'
    success_url = reverse_lazy('inventory:product_category_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(ProductCategory, 'code', organization=organization, prefix='PC')
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Product Category "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class ProductCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'Inventory/product_form.html'
    permission_required = 'Inventory.add_product'
    success_url = reverse_lazy('inventory:product_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(Product, 'code', organization=organization, prefix='PROD')
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Product "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class WarehouseCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'Inventory/warehouse_form.html'
    permission_required = 'Inventory.add_warehouse'
    success_url = reverse_lazy('inventory:warehouse_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(Warehouse, 'code', organization=organization, prefix='WH')
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Warehouse "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class LocationCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Location
    form_class = LocationForm
    template_name = 'Inventory/location_form.html'
    permission_required = 'Inventory.add_location'
    success_url = reverse_lazy('inventory:location_list')

    # If you want auto-code, inject here once a warehouse-scoped generator is defined.

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        organization = self.get_organization()
        if organization:
            form.fields['warehouse'].queryset = form.fields['warehouse'].queryset.filter(
                organization=organization
            )
        return form

    def form_valid(self, form):
        messages.success(self.request, f'Location "{form.instance.name or form.instance.code}" created successfully.')
        return super().form_valid(form)


class PriceListCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = PriceList
    form_class = PriceListForm
    template_name = 'Inventory/pricelist_form.html'
    permission_required = 'Inventory.add_pricelist'
    success_url = reverse_lazy('inventory:pricelist_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(PriceList, 'code', organization=organization, prefix='PL')
            initial['code'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Price List "{form.instance.name}" created successfully.')
        return super().form_valid(form)


class PickListCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = PickList
    form_class = PickListForm
    template_name = 'Inventory/picklist_form.html'
    permission_required = 'Inventory.add_picklist'
    success_url = reverse_lazy('inventory:picklist_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(PickList, 'pick_list_number', organization=organization, prefix='PICK')
            initial['pick_list_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Pick List "{form.instance.pick_list_number}" created successfully.')
        return super().form_valid(form)


class ShipmentCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = Shipment
    form_class = ShipmentForm
    template_name = 'Inventory/shipment_form.html'
    permission_required = 'Inventory.add_shipment'
    success_url = reverse_lazy('inventory:shipment_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(Shipment, 'shipment_number', organization=organization, prefix='SHIP')
            initial['shipment_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'Shipment "{form.instance.shipment_number}" created successfully.')
        return super().form_valid(form)


class RMACreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = RMA
    form_class = RMAForm
    template_name = 'Inventory/rma_form.html'
    permission_required = 'Inventory.add_rma'
    success_url = reverse_lazy('inventory:rma_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(RMA, 'rma_number', organization=organization, prefix='RMA')
            initial['rma_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'RMA "{form.instance.rma_number}" created successfully.')
        return super().form_valid(form)


class BillOfMaterialCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = BillOfMaterial
    form_class = BillOfMaterialForm
    template_name = 'Inventory/billofmaterial_form.html'
    permission_required = 'Inventory.add_billofmaterial'
    success_url = reverse_lazy('inventory:bom_list')

    def get_initial(self):
        initial = super().get_initial()
        organization = self.get_organization()
        if organization:
            code_gen = AutoIncrementCodeGenerator(BillOfMaterial, 'bom_number', organization=organization, prefix='BOM')
            initial['bom_number'] = code_gen.generate_code()
        return initial

    def form_valid(self, form):
        organization = self.get_organization()
        form.instance.organization = organization
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, f'BOM "{form.instance.bom_number}" created successfully.')
        return super().form_valid(form)
