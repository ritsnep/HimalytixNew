# Inventory/forms.py
"""
Forms for Inventory vertical models
Following the same pattern as accounting forms with BootstrapFormMixin
"""
from django import forms
from .models import (
    Product, ProductCategory, Warehouse, Location, Unit, ProductUnit,
    PriceList, PriceListItem, CustomerPriceList, PromotionRule,
    PickList, PickListLine, PackingSlip, Shipment, Backorder, RMA,
    TransitWarehouse, InventoryItem, StockLedger, StockAdjustment, StockAdjustmentLine,
    TransferOrder, TransferOrderLine, Batch
)
from enterprise.models import BillOfMaterial, BillOfMaterialItem
from accounting.forms_mixin import BootstrapFormMixin
from accounting.models import ChartOfAccount


class ProductCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ('code', 'name', 'parent', 'is_active')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    def __init__(self, *args, organization=None, **kwargs):
        # Allow caller (views) to pass organization so we can filter/query defaults
        if organization is not None and not getattr(self, 'organization', None):
            self.organization = organization
        super().__init__(*args, organization=organization, **kwargs)

        # Filter GL account fields to this organization when available
        org = getattr(self, 'organization', None)
        if org:
            try:
                coa_qs = ChartOfAccount.objects.filter(organization=org, is_active=True)
                # Narrow the account choices for each field where it makes sense
                if 'income_account' in self.fields:
                    self.fields['income_account'].queryset = coa_qs.filter(account_type__nature='income')
                if 'expense_account' in self.fields:
                    self.fields['expense_account'].queryset = coa_qs.filter(account_type__nature='expense')
                if 'inventory_account' in self.fields:
                    # Prefer accounts marked as control 'inventory' if present, else asset nature
                    inv_control = coa_qs.filter(is_control_account=True, control_account_type='inventory')
                    if inv_control.exists():
                        self.fields['inventory_account'].queryset = inv_control
                    else:
                        self.fields['inventory_account'].queryset = coa_qs.filter(account_type__nature='asset')

                # Apply sensible initial defaults if not provided by caller
                if not self.initial.get('costing_method') and 'costing_method' in self.fields:
                    self.initial['costing_method'] = self.fields['costing_method'].initial or self.fields['costing_method'].choices[0][0]

                # Default GL picks: pick first available for each
                if 'income_account' in self.fields and not self.initial.get('income_account'):
                    first = self.fields['income_account'].queryset.first()
                    if first:
                        self.initial['income_account'] = first.pk
                if 'expense_account' in self.fields and not self.initial.get('expense_account'):
                    first = self.fields['expense_account'].queryset.first()
                    if first:
                        self.initial['expense_account'] = first.pk
                if 'inventory_account' in self.fields and not self.initial.get('inventory_account'):
                    first = self.fields['inventory_account'].queryset.first()
                    if first:
                        self.initial['inventory_account'] = first.pk
            except Exception:
                # Fail gracefully if accounting app isn't fully migrated or queries fail
                pass
    class Meta:
        model = Product
        fields = (
            'category', 'code', 'name', 'description', 'base_unit', 'sale_price',
            'cost_price', 'currency_code', 'income_account', 'expense_account',
            'inventory_account', 'costing_method', 'standard_cost', 'is_inventory_item',
            'min_order_quantity', 'reorder_level', 'preferred_vendor', 'weight',
            'weight_unit', 'length', 'width', 'height', 'barcode', 'sku'
        )
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'base_unit': forms.Select(attrs={'class': 'form-select'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control'}),
            'income_account': forms.Select(attrs={'class': 'form-select'}),
            'expense_account': forms.Select(attrs={'class': 'form-select'}),
            'inventory_account': forms.Select(attrs={'class': 'form-select'}),
            'costing_method': forms.Select(attrs={'class': 'form-select'}),
            'standard_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_inventory_item': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_order_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'preferred_vendor': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'weight_unit': forms.Select(attrs={'class': 'form-select'}),
            'length': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'width': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'height': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_inventory_item = cleaned_data.get('is_inventory_item')
        costing_method = cleaned_data.get('costing_method')
        
        if is_inventory_item and not costing_method:
            raise forms.ValidationError("Costing method is required for inventory items.")
        
        return cleaned_data


    def __init__(self, *args, organization=None, **kwargs):
        # Allow passing organization from views (UserOrganizationMixin does not do this
        # by default for CreateView, so callers may need to pass it explicitly).
        self.organization = organization or kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Limit GL account querysets to the current organization and active accounts
        try:
            org = self.organization
            if org:
                coa_qs = ChartOfAccount.objects.filter(organization=org, is_active=True)
            else:
                coa_qs = ChartOfAccount.objects.filter(is_active=True)
        except Exception:
            coa_qs = ChartOfAccount.objects.none()

        if 'income_account' in self.fields:
            self.fields['income_account'].queryset = coa_qs.filter(account_type__nature='income')
            # set sensible default if none provided
            if not self.initial.get('income_account') and self.fields['income_account'].queryset.exists():
                self.initial.setdefault('income_account', self.fields['income_account'].queryset.order_by('account_code').first().pk)

        if 'expense_account' in self.fields:
            self.fields['expense_account'].queryset = coa_qs.filter(account_type__nature='expense')
            if not self.initial.get('expense_account') and self.fields['expense_account'].queryset.exists():
                self.initial.setdefault('expense_account', self.fields['expense_account'].queryset.order_by('account_code').first().pk)

        if 'inventory_account' in self.fields:
            # Prefer control account of type 'inventory' if available, otherwise fall back to asset accounts
            inv_qs = coa_qs.filter(control_account_type='inventory')
            if not inv_qs.exists():
                inv_qs = coa_qs.filter(account_type__nature='asset')
            self.fields['inventory_account'].queryset = inv_qs
            if not self.initial.get('inventory_account') and inv_qs.exists():
                self.initial.setdefault('inventory_account', inv_qs.order_by('account_code').first().pk)

        # Ensure costing method has a default initial shown in the form
        if 'costing_method' in self.fields and not self.initial.get('costing_method'):
            from .models import CostingMethod
            self.initial.setdefault('costing_method', CostingMethod.WEIGHTED_AVERAGE)


class UnitForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Unit
        fields = ('code', 'name', 'description', 'is_active')
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductUnitForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductUnit
        fields = ('product', 'unit', 'conversion_factor', 'is_default')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'conversion_factor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WarehouseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = (
            'code', 'name', 'address_line1', 'city', 'country_code',
            'inventory_account', 'is_active'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country_code': forms.TextInput(attrs={'class': 'form-control'}),
            'inventory_account': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class LocationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Location
        fields = ('warehouse', 'code', 'name', 'location_type', 'is_active')
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PriceListForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PriceList
        fields = (
            'code', 'name', 'description', 'currency_code',
            'valid_from', 'valid_to', 'is_active'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PriceListItemForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PriceListItem
        fields = ('product', 'unit_price', 'min_quantity', 'max_quantity', 'discount_percent')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'max_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class PromotionRuleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PromotionRule
        fields = (
            'code', 'name', 'description', 'promo_type',
            'discount_value', 'min_purchase_amount', 'valid_from', 'valid_to',
            'is_active', 'max_uses'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'promo_type': forms.Select(attrs={'class': 'form-select'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'min_purchase_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-control datepicker'}),
            'valid_to': forms.DateTimeInput(attrs={'class': 'form-control datepicker'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_uses': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class PickListForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PickList
        fields = (
            'pick_number', 'warehouse', 'order_reference',
            'assigned_to', 'pick_date', 'status', 'priority', 'notes'
        )
        widgets = {
            'pick_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'order_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'assigned_to': forms.NumberInput(attrs={'class': 'form-control'}),
            'pick_date': forms.DateTimeInput(attrs={'class': 'form-control datepicker'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PickListLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PickListLine
        fields = ('product', 'location', 'batch', 'quantity_ordered', 'quantity_picked', 'line_number')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'quantity_ordered': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'quantity_picked': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'line_number': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ShipmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Shipment
        fields = (
            'shipment_number', 'order_reference', 'ship_from_warehouse', 'ship_to_address',
            'carrier_name', 'tracking_number', 'service_type', 'estimated_delivery',
            'actual_delivery', 'shipping_cost', 'status', 'notes'
        )
        widgets = {
            'shipment_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'order_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'ship_from_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'ship_to_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'carrier_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control'}),
            'service_type': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_delivery': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'actual_delivery': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class RMAForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RMA
        fields = (
            'rma_number', 'customer_id', 'original_order', 'original_invoice',
            'reason', 'description', 'status', 'resolution',
            'refund_amount', 'restocking_fee', 'notes'
        )
        widgets = {
            'rma_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'customer_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'original_order': forms.TextInput(attrs={'class': 'form-control'}),
            'original_invoice': forms.TextInput(attrs={'class': 'form-control'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'resolution': forms.TextInput(attrs={'class': 'form-control'}),
            'refund_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'restocking_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BillOfMaterialForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BillOfMaterial
        fields = ('name', 'product_name', 'revision')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'product_name': forms.TextInput(attrs={'class': 'form-control'}),
            'revision': forms.TextInput(attrs={'class': 'form-control'}),
        }


class BOMLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BillOfMaterialItem
        fields = ('component_name', 'quantity', 'uom')
        widgets = {
            'component_name': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'uom': forms.TextInput(attrs={'class': 'form-control'}),
        }


# Inline formsets
PickListLineFormSet = forms.inlineformset_factory(
    PickList, PickListLine,
    form=PickListLineForm,
    extra=1,
    can_delete=True
)

BOMLineFormSet = forms.inlineformset_factory(
    BillOfMaterial, BillOfMaterialItem,
    form=BOMLineForm,
    extra=1,
    can_delete=True
)


class BaseStockTransactionForm(BootstrapFormMixin, forms.Form):
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
        self.fields['quantity'].widget.attrs['step'] = '0.0001'

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


class StockReceiptForm(BaseStockTransactionForm):
    unit_cost = forms.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        label="Unit Cost",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'})
    )


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


class TransferOrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TransferOrder
        fields = (
            'order_number', 'source_warehouse', 'destination_warehouse',
            'reference_id', 'scheduled_date', 'notes', 'instructions', 'pick_list'
        )
        widgets = {
            'order_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'source_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'destination_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'reference_id': forms.TextInput(attrs={'class': 'form-control'}),
            'scheduled_date': forms.DateTimeInput(attrs={'class': 'form-control datepicker'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'pick_list': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if self.organization:
            wh_qs = Warehouse.objects.filter(organization=self.organization, is_active=True)
            self.fields['source_warehouse'].queryset = wh_qs
            self.fields['destination_warehouse'].queryset = wh_qs
            self.fields['destination_warehouse'].empty_label = "Select destination"
            self.fields['source_warehouse'].empty_label = "Select source"
            self.fields['pick_list'].queryset = PickList.objects.filter(
                organization=self.organization
            ).order_by('-created_at')
            self.fields['pick_list'].required = False


class TransferOrderLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TransferOrderLine
        fields = (
            'product', 'from_location', 'to_location', 'batch',
            'quantity_requested', 'notes'
        )
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'from_location': forms.Select(attrs={'class': 'form-select'}),
            'to_location': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'quantity_requested': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['product'].queryset = Product.objects.filter(
                organization=self.organization,
                is_inventory_item=True
            ).order_by('name')
            loc_qs = Location.objects.filter(
                warehouse__organization=self.organization,
                is_active=True
            ).order_by('warehouse__name', 'code')
            self.fields['from_location'].queryset = loc_qs
            self.fields['to_location'].queryset = loc_qs
            self.fields['from_location'].required = False
            self.fields['to_location'].required = False
            self.fields['batch'].queryset = Batch.objects.filter(
                organization=self.organization
            ).order_by('product__code', 'batch_number')


TransferOrderLineFormSet = forms.inlineformset_factory(
    TransferOrder,
    TransferOrderLine,
    form=TransferOrderLineForm,
    extra=1,
    can_delete=True
)


class TransferOrderFilterForm(forms.Form):
    status = forms.MultipleChoiceField(
        choices=TransferOrder.STATUS_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Status"
    )
    source_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        required=False,
        label="Source Warehouse"
    )
    destination_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        required=False,
        label="Destination Warehouse"
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            qs = Warehouse.objects.filter(organization=organization, is_active=True)
            self.fields['source_warehouse'].queryset = qs
            self.fields['destination_warehouse'].queryset = qs

class ReorderRecommendationFilterForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        required=False,
        label="Warehouse"
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(
                organization=organization, is_active=True
            )

class StockAdjustmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ('adjustment_number', 'warehouse', 'reason', 'reference_id', 'notes')
        widgets = {
            'adjustment_number': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'reference_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['warehouse'].queryset = Warehouse.objects.filter(
                organization=self.organization, is_active=True
            ).order_by('name')


class StockAdjustmentLineForm(BootstrapFormMixin, forms.ModelForm):
    system_quantity = forms.DecimalField(
        max_digits=15,
        decimal_places=4,
        required=False,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.0001', 'readonly': True}
        ),
        initial=0,
    )

    class Meta:
        model = StockAdjustmentLine
        fields = ('product', 'location', 'batch', 'counted_quantity', 'system_quantity', 'notes')
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.Select(attrs={'class': 'form-select'}),
            'batch': forms.Select(attrs={'class': 'form-select'}),
            'counted_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['product'].queryset = Product.objects.filter(
                organization=self.organization, is_inventory_item=True
            ).order_by('name')
            self.fields['location'].queryset = Location.objects.filter(
                warehouse__organization=self.organization,
                is_active=True
            ).order_by('warehouse__name', 'code')
            self.fields['batch'].queryset = Batch.objects.filter(
                organization=self.organization
            ).order_by('product__code', 'batch_number')
        self.fields['location'].required = False
        self.fields['batch'].required = False


StockAdjustmentLineFormSet = forms.inlineformset_factory(
    StockAdjustment,
    StockAdjustmentLine,
    form=StockAdjustmentLineForm,
    extra=1,
    can_delete=True
)
