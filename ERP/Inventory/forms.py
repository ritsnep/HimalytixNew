from django import forms
from django.forms import ModelForm
from .models import ProductCategory, Product, Warehouse, Location
from accounting.models import ChartOfAccount

class ProductCategoryForm(ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['code', 'name', 'parent', 'is_active']

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # Limit parent choices to categories within the same organization
        if organization:
            self.fields['parent'].queryset = ProductCategory.objects.filter(organization=organization)
        # Add Tailwind classes
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'

class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = [
            'category', 'code', 'name', 'description', 'uom', 'sale_price',
            'cost_price', 'currency_code', 'income_account', 'expense_account',
            'inventory_account', 'is_inventory_item', 'min_order_quantity',
            'reorder_level', 'preferred_vendor_id', 'barcode', 'sku'
        ]

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # Limit FK choices to objects within the same organization
        if organization:
            self.fields['category'].queryset = ProductCategory.objects.filter(organization=organization)
            self.fields['income_account'].queryset = ChartOfAccount.objects.filter(organization=organization)
            self.fields['expense_account'].queryset = ChartOfAccount.objects.filter(organization=organization)
            self.fields['inventory_account'].queryset = ChartOfAccount.objects.filter(organization=organization)

        # Add Tailwind classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                 field.widget.attrs['class'] = 'h-4 w-4 text-indigo-600 border-gray-300 rounded'
            else:
                field.widget.attrs['class'] = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'

class WarehouseForm(ModelForm):
    class Meta:
        model = Warehouse
        fields = [
            'code', 'name', 'address_line1', 'city', 'country_code',
            'inventory_account', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # Limit FK choices to objects within the same organization
        if organization:
            self.fields['inventory_account'].queryset = ChartOfAccount.objects.filter(organization=organization)

        # Add Tailwind classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                 field.widget.attrs['class'] = 'h-4 w-4 text-indigo-600 border-gray-300 rounded'
            else:
                field.widget.attrs['class'] = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'

class LocationForm(ModelForm):
    class Meta:
        model = Location
        fields = ['warehouse', 'code', 'name', 'location_type', 'is_active']

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # Limit warehouse choices to warehouses within the same organization
        if organization:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(organization=organization)

        # Add Tailwind classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                 field.widget.attrs['class'] = 'h-4 w-4 text-indigo-600 border-gray-300 rounded'
            else:
                field.widget.attrs['class'] = 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
