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


class BaseStockTransactionForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.none(), label="Product")
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.none(), label="Warehouse")
    location = forms.ModelChoiceField(
        queryset=Location.objects.none(),
        label="Location",
        required=False,
        help_text="Optional bin/location within the selected warehouse."
    )
    batch_number = forms.CharField(required=False, label="Batch Number")
    serial_number = forms.CharField(required=False, label="Serial Number")
    reference_id = forms.CharField(
        max_length=100,
        label="Reference",
        help_text="Shown in the stock ledger so you can tie back to paperwork."
    )
    quantity = forms.DecimalField(
        max_digits=15,
        decimal_places=4,
        min_value=0.0001,
        label="Quantity"
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['product'].queryset = Product.objects.filter(
                organization=self.organization,
                is_inventory_item=True
            ).order_by('name')
            self.fields['warehouse'].queryset = Warehouse.objects.filter(
                organization=self.organization,
                is_active=True
            ).order_by('name')
            self.fields['location'].queryset = Location.objects.filter(
                warehouse__organization=self.organization,
                is_active=True
            ).order_by('warehouse__name', 'code')

        self.fields['location'].empty_label = "Optional"
        self._apply_tailwind_styles()

    def clean(self):
        cleaned_data = super().clean()
        batch = cleaned_data.get('batch_number')
        serial = cleaned_data.get('serial_number')
        warehouse = cleaned_data.get('warehouse')
        location = cleaned_data.get('location')
        if serial and not batch:
            self.add_error('batch_number', 'Provide a batch number when adding a serial number.')
        if location and warehouse and location.warehouse_id != warehouse.id:
            self.add_error('location', 'Select a location that belongs to the chosen warehouse.')
        return cleaned_data

    def _apply_tailwind_styles(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'h-4 w-4 text-indigo-600 border-gray-300 rounded'
            else:
                base_class = widget.attrs.get('class', '')
                widget.attrs['class'] = (
                    base_class + ' mt-1 block w-full rounded-md border-gray-300 '
                    'shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
                ).strip()
        # Fine tune numeric inputs for quicker entry
        self.fields['quantity'].widget.attrs['step'] = '0.0001'


class StockReceiptForm(BaseStockTransactionForm):
    unit_cost = forms.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        label="Unit Cost"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['unit_cost'].widget.attrs.setdefault('step', '0.0001')


class StockIssueForm(BaseStockTransactionForm):
    reason = forms.CharField(
        required=False,
        label="Reason",
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text="Optional description displayed in the ledger reference alongside your reference code."
    )

    def _apply_tailwind_styles(self):
        super()._apply_tailwind_styles()
        self.fields['reason'].widget.attrs['rows'] = 2
