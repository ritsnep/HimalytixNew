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
    class Meta:
        model = PurchaseInvoice
        fields = (
            'organization',
            'vendor',
            'invoice_number',
            'external_reference',
            'invoice_date',
            'due_date',
            'payment_term',
            'currency',
            'exchange_rate',
            'po_number',
            'receipt_reference',
            'notes',
        )
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'form-control'}),
            'external_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'due_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'payment_term': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'po_number': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['invoice_number'].required = False
        self.fields['invoice_number'].widget.attrs.setdefault('placeholder', 'Auto-generated')
        self.fields['invoice_number'].widget.attrs['readonly'] = True
        if self.organization:
            self.fields['vendor'].queryset = self.fields['vendor'].queryset.filter(
                organization=self.organization
            )

    def clean(self):
        cleaned = super().clean()
        vendor = cleaned.get('vendor') or getattr(self.instance, 'vendor', None)
        payment_term = cleaned.get('payment_term') or getattr(vendor, 'payment_term', None)
        invoice_date = cleaned.get('invoice_date')
        due_date = cleaned.get('due_date')
        if invoice_date and not due_date and payment_term:
            cleaned['due_date'] = payment_term.calculate_due_date(invoice_date)
        return cleaned


class PurchaseInvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseInvoiceLine
        fields = (
            'description',
            'product_code',
            'quantity',
            'unit_cost',
            'discount_amount',
            'account',
            'tax_code',
            'tax_amount',
            'cost_center',
            'department',
            'project',
            'dimension_value',
            'po_reference',
            'receipt_reference',
        )
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'product_code': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'account': forms.Select(attrs={'class': 'form-select'}),
            'tax_code': forms.Select(attrs={'class': 'form-select'}),
            'tax_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_center': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'dimension_value': forms.Select(attrs={'class': 'form-select'}),
            'po_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_reference': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['account'].queryset = ChartOfAccount.objects.filter(organization=self.organization)
            self.fields['tax_code'].queryset = TaxCode.objects.filter(organization=self.organization)
            self.fields['cost_center'].queryset = CostCenter.objects.filter(organization=self.organization)
            self.fields['department'].queryset = Department.objects.filter(organization=self.organization)
            self.fields['project'].queryset = Project.objects.filter(organization=self.organization)
            self.fields['dimension_value'].queryset = DimensionValue.objects.filter(
                dimension__organization=self.organization
            )


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
