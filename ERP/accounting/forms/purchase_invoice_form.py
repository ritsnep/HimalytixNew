from decimal import Decimal
import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F

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
from utils.calendars import maybe_coerce_bs_date
from utils.widgets import dual_date_widget


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
    allow_credit_override = forms.BooleanField(required=False, help_text="Override credit limit for this invoice")
    invoice_date = forms.DateField(required=False)
    due_date = forms.DateField(required=False)
    
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
        self.fields['discount_amount'].required = False
        self.fields['discount_percentage'].required = False
        if self.fields['discount_amount'].initial is None:
            self.fields['discount_amount'].initial = Decimal('0')
        if self.fields['discount_percentage'].initial is None:
            self.fields['discount_percentage'].initial = Decimal('0')
        self.fields['invoice_number'].required = False
        self.fields['invoice_number'].widget.attrs.setdefault('placeholder', 'Auto-generated')
        self.fields['invoice_number'].widget.attrs['readonly'] = True
        self.fields['grir_account'].required = False
        self.fields['grir_account'].help_text = 'GR/IR clearing account for inventory receipts'
        self.fields['invoice_date'].required = False
        self.fields['due_date'].required = False
        try:
            invoice_dual_widget = dual_date_widget(organization=self.organization, default_view='DUAL')
            due_dual_widget = dual_date_widget(organization=self.organization, default_view='DUAL')
            self.fields['invoice_date'].widget = invoice_dual_widget
            self.fields['due_date'].widget = due_dual_widget
        except Exception:
            pass
        if self.organization:
            self.fields['vendor'].queryset = self.fields['vendor'].queryset.filter(
                organization=self.organization
            )
            purchase_account_qs = ChartOfAccount.objects.filter(
                organization=self.organization, 
                is_active=True,
                account_type__nature='expense'
            )
            self.fields['purchase_account'].queryset = purchase_account_qs
            # Auto-select first expense account if available
            if purchase_account_qs.exists() and not self.instance.pk:
                self.fields['purchase_account'].initial = purchase_account_qs.first()
            self.fields['grir_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization, is_active=True
            )

    def _post_clean(self):
        # Set default dates to avoid model validation errors when form has date errors
        if (not self.is_bound) and not self.instance.invoice_date:
            self.instance.invoice_date = timezone.now().date()
        if (not self.is_bound) and not self.instance.due_date:
            self.instance.due_date = timezone.now().date()
        super()._post_clean()

        if self.instance and (self.instance.discount_percentage or self.instance.discount_amount):
            if self.instance.discount_percentage:
                self.fields['discount_type'].initial = 'percent'
                self.fields['discount_value'].initial = self.instance.discount_percentage
            else:
                self.fields['discount_type'].initial = 'amount'
                self.fields['discount_value'].initial = self.instance.discount_amount
    def _tolerant_date_field(self, cleaned, field_name):
        """Try to coerce multiple incoming date formats into a date on `cleaned`.

        Handles:
        - Already-cleaned date objects
        - Explicit BS field submitted via DualCalendarWidget (`<field>_bs`)
        - Nepali numerals and BS strings via `maybe_coerce_bs_date`
        - Common AD formats: ISO, MM/DD/YYYY, DD-MM-YYYY, DD/MM/YYYY
        """
        current_value = cleaned.get(field_name)
        if isinstance(current_value, (datetime.date, datetime.datetime)):
            return current_value

        # 1) Prefer widget-submitted AD value (already bound) or BS companion
        raw = self.data.get(field_name)
        if not raw:
            # Try BS companion field produced by DualCalendarWidget
            raw = self.data.get(f"{field_name}_bs") or self.data.get(f"{field_name}-bs")

        if not raw:
            return None

        s = str(raw).strip()

        # 2) If it looks like a BS string, try coercion
        bs_coerced = maybe_coerce_bs_date(s)
        if bs_coerced:
            cleaned[field_name] = bs_coerced
            # clear any previous field errors
            if getattr(self, '_errors', None) and field_name in self._errors:
                del self._errors[field_name]
            return bs_coerced

        # 3) Try common AD formats
        candidates = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d-%m-%Y',
            '%d/%m/%Y',
        ]
        for fmt in candidates:
            try:
                dt = datetime.datetime.strptime(s, fmt).date()
                cleaned[field_name] = dt
                if getattr(self, '_errors', None) and field_name in self._errors:
                    del self._errors[field_name]
                return dt
            except Exception:
                continue

        # 4) As a last resort, try Django's parse_date
        from django.utils.dateparse import parse_date
        parsed = parse_date(s)
        if parsed:
            cleaned[field_name] = parsed
            if getattr(self, '_errors', None) and field_name in self._errors:
                del self._errors[field_name]
            return parsed

        # 5) Give a clear field error
        field = self.fields.get(field_name)
        label = field.label if field and field.label else field_name.replace('_', ' ')
        self.add_error(field_name, f"Invalid {label} format; please use YYYY-MM-DD, DD-MM-YYYY, MM/DD/YYYY, or toggle AD/BS.")
        return None

    def clean(self):
        cleaned = super().clean()

        # Convert BS dates to AD if AD fields are missing
        if not cleaned.get('invoice_date') and self.data.get('invoice_date_bs'):
            ad_date = maybe_coerce_bs_date(str(self.data.get('invoice_date_bs')))
            if ad_date:
                cleaned['invoice_date'] = ad_date
            else:
                self.add_error('invoice_date', 'Invalid Bikram Sambat date.')

        if not cleaned.get('due_date') and self.data.get('due_date_bs'):
            ad_date = maybe_coerce_bs_date(str(self.data.get('due_date_bs')))
            if ad_date:
                cleaned['due_date'] = ad_date
            else:
                self.add_error('due_date', 'Invalid Bikram Sambat date.')

        self._tolerant_date_field(cleaned, 'invoice_date')
        self._tolerant_date_field(cleaned, 'due_date')

        invoice_date = cleaned.get('invoice_date')
        due_date = cleaned.get('due_date')
        discount_value = cleaned.get('discount_value')
        discount_type = cleaned.get('discount_type') or 'amount'
        if discount_value is not None:
            if discount_type == 'percent':
                cleaned['discount_percentage'] = discount_value
                cleaned['discount_amount'] = 0
            else:
                cleaned['discount_amount'] = discount_value
                cleaned['discount_percentage'] = 0
        if cleaned.get('discount_amount') is None:
            cleaned['discount_amount'] = Decimal('0')
        if cleaned.get('discount_percentage') is None:
            cleaned['discount_percentage'] = Decimal('0')
        vendor = cleaned.get('vendor') or getattr(self.instance, 'vendor', None)
        payment_term = cleaned.get('payment_term') or getattr(vendor, 'payment_term', None)
        if invoice_date and not due_date and payment_term:
            cleaned['due_date'] = payment_term.calculate_due_date(invoice_date)
            due_date = cleaned['due_date']
        elif invoice_date and not due_date:
            cleaned['due_date'] = invoice_date
            due_date = cleaned['due_date']

        if not invoice_date:
            self.add_error('invoice_date', 'Invoice date is required.')

        default_currency = getattr(self.organization, 'base_currency_code', None)
        currency = cleaned.get('currency')
        exchange_rate = cleaned.get('exchange_rate')
        purchase_account = cleaned.get('purchase_account')

        if not vendor:
            self.add_error('vendor', 'Please select a supplier.')

        if not currency:
            self.add_error('currency', 'Currency is required.')

        if purchase_account is None:
            self.add_error('purchase_account', 'Please choose a purchase account.')

        if (
            invoice_date
            and due_date
            and due_date < invoice_date
        ):
            self.add_error('due_date', 'Due date must be on or after the invoice date.')

        if currency and default_currency and currency != default_currency:
            if exchange_rate is None or exchange_rate <= 0:
                self.add_error('exchange_rate', 'Exchange rate must be greater than zero when using a foreign currency.')
        elif exchange_rate is not None and exchange_rate <= 0:
            self.add_error('exchange_rate', 'Exchange rate must be greater than zero.')

        # Flag credit override into metadata for downstream checks
        if getattr(self.instance, "metadata", None) is None:
            self.instance.metadata = {}
        if cleaned.get("allow_credit_override"):
            self.instance.metadata["allow_credit_override"] = True
        else:
            self.instance.metadata.pop("allow_credit_override", None)

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
            'input_vat_account',
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
            'input_vat_account': forms.Select(attrs={'class': 'form-select form-select-sm vat-account-select'}),
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
            self.fields['input_vat_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization, is_active=True
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
        for field_name in ['product', 'warehouse', 'tax_code', 'cost_center', 'department', 'project', 'dimension_value', 'product_name', 'unit_display', 'input_vat_account']:
            if field_name in self.fields:
                self.fields[field_name].required = False
        
        # Set VAT rate default
        if 'vat_rate' in self.fields and not self.instance.vat_rate:
            self.fields['vat_rate'].initial = 13.00

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None or qty <= 0:
            raise ValidationError('Quantity must be greater than zero.')
        return qty

    def clean_unit_cost(self):
        rate = self.cleaned_data.get('unit_cost')
        if rate is None or rate < 0:
            raise ValidationError('Unit cost cannot be negative.')
        return rate

    def clean(self):
        cleaned = super().clean()
        description = cleaned.get('description')
        product = cleaned.get('product')
        if not product and not description:
            self.add_error(None, 'Either a product or description is required.')

        qty = cleaned.get('quantity') or 0
        rate = cleaned.get('unit_cost') or 0
        discount_amount = cleaned.get('discount_amount') or 0
        if discount_amount < 0:
            self.add_error('discount_amount', 'Discount cannot be negative.')
        max_discount = qty * rate
        if discount_amount and max_discount and discount_amount > max_discount:
            self.add_error('discount_amount', 'Discount cannot exceed the line amount.')

        vat_rate = cleaned.get('vat_rate')
        if vat_rate is not None and (vat_rate < 0 or vat_rate > 100):
            self.add_error('vat_rate', 'VAT rate must be between 0 and 100.')

        net_amount = (qty * rate) - (discount_amount or 0)
        vat_rate_decimal = Decimal(str(vat_rate or 0))
        line_tax = cleaned.get('tax_amount') or Decimal('0')
        if vat_rate_decimal > 0:
            net = net_amount if net_amount > 0 else Decimal('0')
            line_tax = (net * (vat_rate_decimal / Decimal('100'))).quantize(Decimal('0.01'))
            cleaned['tax_amount'] = line_tax
        elif line_tax:
            cleaned['tax_amount'] = Decimal(str(line_tax)).quantize(Decimal('0.01'))

        if (vat_rate_decimal > 0) or (line_tax and line_tax > 0):
            if not cleaned.get('input_vat_account'):
                tax_code = cleaned.get('tax_code')
                auto_account = getattr(tax_code, 'purchase_account', None) if tax_code else None
                if auto_account:
                    cleaned['input_vat_account'] = auto_account
                else:
                    self.add_error('input_vat_account', 'Input VAT account is required when VAT is applied.')

        if product and getattr(product, 'is_inventory_item', False) and not cleaned.get('warehouse'):
            self.add_error('warehouse', 'Please select a warehouse for an inventory item.')

        return cleaned


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
