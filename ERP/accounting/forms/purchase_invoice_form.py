from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounting.forms_mixin import BootstrapFormMixin
from accounting.models import (
    ChartOfAccount,
    CostCenter,
    Currency,
    Department,
    DimensionValue,
    Project,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    TaxCode,
    Vendor,
    Customer,
)


class PurchaseInvoiceForm(BootstrapFormMixin, forms.ModelForm):
    # Declare warehouse fields manually to avoid circular import at class definition time
    warehouse = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Required when receiving inventory items'
    )
    discount_value = forms.DecimalField(
        required=False,
        max_digits=19,
        decimal_places=4,
        widget=forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.01'})
    )
    discount_type = forms.ChoiceField(
        required=False,
        choices=[('amount', 'Amt'), ('percent', 'Per')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    bill_rounding = forms.DecimalField(
        required=False,
        max_digits=19,
        decimal_places=4,
        widget=forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.01'})
    )
    
    class Meta:
        model = PurchaseInvoice
        fields = (
            'organization',
            'vendor',
            'invoice_number',
            'supplier_invoice_number',
            'external_reference',
            'invoice_date',
            'invoice_date_bs',
            'due_date',
            'payment_term',
            'payment_mode',
            'currency',
            'exchange_rate',
            'purchase_order',
            'po_number',
            'receipt_reference',
            'purchase_account',
            'grir_account',
            'discount_amount',
            'discount_percentage',
            'terms_and_conditions',
            'narration',
            'notes',
        )
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier_invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'external_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'invoice_date_bs': forms.TextInput(attrs={'class': 'form-control'}),
            'due_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'purchase_order': forms.Select(attrs={'class': 'form-select'}),
            'po_number': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'purchase_account': forms.Select(attrs={'class': 'form-select'}),
            'grir_account': forms.Select(attrs={'class': 'form-select'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.01'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control text-end', 'step': '0.01'}),
            'terms_and_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'narration': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['invoice_number'].required = False
        self.fields['invoice_number'].widget.attrs.setdefault('placeholder', 'Auto-generated')
        self.fields['invoice_number'].widget.attrs['readonly'] = True
        self.fields['grir_account'].required = False
        self.fields['grir_account'].help_text = 'GR/IR clearing account for inventory receipts'
        if self.organization:
            self.fields['vendor'].queryset = self.fields['vendor'].queryset.filter(
                organization=self.organization
            )
            # Filter warehouses by organization
            from inventory.models import Warehouse
            self.fields['warehouse'].queryset = Warehouse.objects.filter(
                organization=self.organization, is_active=True
            )
            # Filter GL accounts by organization
            self.fields['grir_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization, is_active=True
            )
            # Purchase-order and purchase account support
            try:
                from purchasing.models import PurchaseOrder
                self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(organization=self.organization, status='open')
            except Exception:
                # If purchasing app not present, leave as empty queryset
                self.fields['purchase_order'].queryset = self.fields.get('purchase_order').queryset

            self.fields['purchase_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization, is_active=True
            )
            # payment_mode is on model with choices; no queryset needed
            # Set default values if missing
            if 'payment_mode' in self.fields and not self.fields['payment_mode'].initial:
                self.fields['payment_mode'].initial = 'credit'
        # Initialize header discount helpers from model values
        if self.instance and (self.instance.discount_percentage or self.instance.discount_amount):
            if self.instance.discount_percentage:
                self.fields['discount_type'].initial = 'percent'
                self.fields['discount_value'].initial = self.instance.discount_percentage
            else:
                self.fields['discount_type'].initial = 'amount'
                self.fields['discount_value'].initial = self.instance.discount_amount

    def clean(self):
        cleaned = super().clean()
        discount_value = cleaned.get('discount_value')
        discount_type = cleaned.get('discount_type') or 'amount'
        if discount_value is not None:
            if discount_type == 'percent':
                cleaned['discount_percentage'] = discount_value
                cleaned['discount_amount'] = 0
            else:
                cleaned['discount_amount'] = discount_value
                cleaned['discount_percentage'] = 0
        vendor = cleaned.get('vendor') or getattr(self.instance, 'vendor', None)
        payment_term = cleaned.get('payment_term') or getattr(vendor, 'payment_term', None)
        invoice_date = cleaned.get('invoice_date')
        due_date = cleaned.get('due_date')
        if invoice_date and not due_date and payment_term:
            cleaned['due_date'] = payment_term.calculate_due_date(invoice_date)
        return cleaned


class PurchaseInvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    product_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'readonly': True}))
    unit_display = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'readonly': True}))
    
    class Meta:
        model = PurchaseInvoiceLine
        fields = (
            'description',
            'product',
            'product_code',
            'quantity',
            'unit_cost',
            'discount_amount',
            'account',
            'tax_code',
            'tax_amount',
            'warehouse',
            'vat_rate',
            'cost_center',
            'department',
            'project',
            'dimension_value',
            'po_reference',
            'receipt_reference',
        )
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'product': forms.Select(attrs={'class': 'form-select form-select-sm product-select'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control form-control-sm product-search'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}),
            'account': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'tax_code': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}),
            'warehouse': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'vat_rate': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01'}),
            'cost_center': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'department': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'project': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'dimension_value': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'po_reference': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'receipt_reference': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            try:
                from inventory.models import Warehouse, Product
                self.fields['warehouse'].queryset = Warehouse.objects.filter(
                    organization=self.organization, is_active=True
                )
                self.fields['product'].queryset = Product.objects.filter(
                    organization=self.organization, is_active=True
                )
            except Exception:
                pass
            
            self.fields['account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization, is_active=True
            )
            self.fields['tax_code'].queryset = TaxCode.objects.filter(
                organization=self.organization
            )
            self.fields['cost_center'].queryset = CostCenter.objects.filter(
                organization=self.organization
            )
            self.fields['department'].queryset = Department.objects.filter(
                organization=self.organization
            )
            self.fields['project'].queryset = Project.objects.filter(
                organization=self.organization
            )
            self.fields['dimension_value'].queryset = DimensionValue.objects.filter(
                dimension__organization=self.organization
            )
        
        # Make optional fields not required
        for field_name in ['product', 'warehouse', 'tax_code', 'cost_center', 'department', 'project', 'dimension_value', 'product_name', 'unit_display']:
            if field_name in self.fields:
                self.fields[field_name].required = False
        
        # Set VAT rate default
        if 'vat_rate' in self.fields and not self.instance.vat_rate:
            self.fields['vat_rate'].initial = 13.00


class VendorStatementFilterForm(BootstrapFormMixin, forms.Form):
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
    )
    start_date = forms.DateField(
        widget=forms.TextInput(attrs={'class': 'form-control datepicker'}),
    )
    end_date = forms.DateField(
        widget=forms.TextInput(attrs={'class': 'form-control datepicker'}),
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        if self.organization:
            self.fields['vendor'].queryset = Vendor.objects.filter(organization=self.organization)
        if not self.initial.get('start_date'):
            self.fields['start_date'].initial = first_of_month
        if not self.initial.get('end_date'):
            self.fields['end_date'].initial = today

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date.")
        return cleaned


class CustomerStatementFilterForm(BootstrapFormMixin, forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
    )
    start_date = forms.DateField(
        widget=forms.TextInput(attrs={'class': 'form-control datepicker'}),
    )
    end_date = forms.DateField(
        widget=forms.TextInput(attrs={'class': 'form-control datepicker'}),
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        if self.organization:
            self.fields['customer'].queryset = Customer.objects.filter(organization=self.organization)
        if not self.initial.get('start_date'):
            self.fields['start_date'].initial = first_of_month
        if not self.initial.get('end_date'):
            self.fields['end_date'].initial = today

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date.")
        return cleaned


PAYMENT_METHOD_CHOICES = [
    ('bank_transfer', 'Bank Transfer'),
    ('cheque', 'Cheque'),
    ('wire_transfer', 'Wire Transfer'),
]


class PaymentSchedulerForm(BootstrapFormMixin, forms.Form):
    batch_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Batch Number",
    )
    scheduled_date = forms.DateField(
        widget=forms.TextInput(attrs={'class': 'form-control datepicker'}),
        label="Scheduled Date",
    )
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    bank_account = forms.ModelChoiceField(
        queryset=ChartOfAccount.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Bank Account",
    )
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='bank_transfer',
    )
    exchange_rate = forms.DecimalField(
        max_digits=19,
        decimal_places=6,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['bank_account'].queryset = ChartOfAccount.objects.filter(
            organization=self.organization,
            is_active=True,
            is_bank_account=True,
        )
        if self.fields['bank_account'].queryset.exists():
            self.fields['bank_account'].initial = self.fields['bank_account'].queryset.first()



# Formset definitions for purchase invoices
from django.forms import inlineformset_factory

PurchaseInvoiceLineFormSet = inlineformset_factory(
    PurchaseInvoice,
    PurchaseInvoiceLine,
    form=PurchaseInvoiceLineForm,
    extra=1,
    can_delete=True,
)

# Note: PurchasePaymentFormSet is not used as APPayment doesn't have FK to PurchaseInvoice
# Payment scheduling should be handled separately
