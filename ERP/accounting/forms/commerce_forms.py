from django import forms

from accounting.forms_mixin import BootstrapFormMixin
from accounting.models import (
    APPayment,
    APPaymentLine,
    Agent,
    ChartOfAccount,
    Currency,
    Customer,
    PaymentTerm,
    PurchaseInvoice,
    SalesInvoice,
    SalesInvoiceLine,
    Vendor,
    ARReceipt,
    ARReceiptLine,
)
from locations.models import LocationNode


def get_active_currency_choices():
    return [
        (currency.currency_code, f"{currency.currency_code} - {currency.currency_name}")
        for currency in Currency.objects.filter(is_active=True)
    ]


class SalesInvoiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesInvoice
        fields = (
            "organization",
            "customer",
            "invoice_number",
            "reference_number",
            "invoice_date",
            "due_date",
            "payment_term",
            "currency",
            "exchange_rate",
            "notes",
        )
        widgets = {
            "invoice_number": forms.TextInput(attrs={"class": "form-control"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control"}),
            "invoice_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "due_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "payment_term": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        self.fields["invoice_number"].required = False
        self.fields["invoice_number"].widget.attrs.setdefault("placeholder", "Auto-generated")
        self.fields["invoice_number"].widget.attrs["readonly"] = True
        if self.organization:
            self.fields["customer"].queryset = self.fields["customer"].queryset.filter(
                organization=self.organization
            )

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer") or getattr(self.instance, "customer", None)
        payment_term = cleaned.get("payment_term") or getattr(customer, "payment_term", None)
        invoice_date = cleaned.get("invoice_date")
        due_date = cleaned.get("due_date")
        if invoice_date and not due_date and payment_term:
            cleaned["due_date"] = payment_term.calculate_due_date(invoice_date)
        return cleaned


class SalesInvoiceLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesInvoiceLine
        fields = (
            "description",
            "product_code",
            "quantity",
            "unit_price",
            "discount_amount",
            "revenue_account",
            "tax_code",
            "tax_amount",
            "cost_center",
            "department",
            "project",
            "dimension_value",
        )
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "product_code": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
            "discount_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "revenue_account": forms.Select(attrs={"class": "form-select"}),
            "tax_code": forms.Select(attrs={"class": "form-select"}),
            "tax_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "project": forms.Select(attrs={"class": "form-select"}),
            "dimension_value": forms.Select(attrs={"class": "form-select"}),
        }


class DeliveryNoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        from accounting.models import DeliveryNote
        model = DeliveryNote
        fields = (
            "organization",
            "customer",
            "note_number",
            "reference_number",
            "delivery_date",
            "warehouse",
            "notes",
        )
        widgets = {
            "note_number": forms.TextInput(attrs={"class": "form-control"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control"}),
            "delivery_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "warehouse": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        self.fields["note_number"].required = False
        self.fields["note_number"].widget.attrs.setdefault("placeholder", "Auto-generated")
        self.fields["note_number"].widget.attrs["readonly"] = True
        if self.organization:
            self.fields["customer"].queryset = self.fields["customer"].queryset.filter(
                organization=self.organization
            )


class DeliveryNoteLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        from accounting.models import DeliveryNoteLine
        model = DeliveryNoteLine
        fields = (
            "description",
            "product",
            "product_code",
            "quantity",
        )
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "product_code": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization:
            # product queryset limited by organization
            self.fields["product"].queryset = self.fields["product"].queryset.filter(organization=self.organization)


class ARReceiptForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ARReceipt
        fields = (
            "organization",
            "customer",
            "receipt_number",
            "receipt_date",
            "payment_method",
            "reference",
            "currency",
            "exchange_rate",
            "amount",
        )
        widgets = {
            "receipt_number": forms.TextInput(attrs={"class": "form-control"}),
            "receipt_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "payment_method": forms.TextInput(attrs={"class": "form-control"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields["customer"].queryset = Customer.objects.filter(organization=self.organization)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)


class ARReceiptLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ARReceiptLine
        fields = ("invoice", "applied_amount", "discount_taken")
        widgets = {
            "invoice": forms.Select(attrs={"class": "form-select"}),
            "applied_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_taken": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        self.customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)
        queryset = SalesInvoice.objects.none()
        if self.organization:
            queryset = SalesInvoice.objects.filter(
                organization=self.organization,
                status__in=["posted", "validated"],
            )
        if self.customer:
            queryset = queryset.filter(customer=self.customer)
        self.fields["invoice"].queryset = queryset


class APPaymentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = APPayment
        fields = (
            "organization",
            "vendor",
            "payment_number",
            "payment_date",
            "payment_method",
            "bank_account",
            "currency",
            "exchange_rate",
            "amount",
            "discount_taken",
            "status",
            "batch",
            "metadata",
        )
        widgets = {
            "payment_number": forms.TextInput(attrs={"class": "form-control"}),
            "payment_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "payment_method": forms.TextInput(attrs={"class": "form-control"}),
            "bank_account": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_taken": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "batch": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields["vendor"].queryset = self.fields["vendor"].queryset.filter(
                organization=self.organization
            )
            self.fields["bank_account"].queryset = self.fields["bank_account"].queryset.filter(
                organization=self.organization
            )
            self.instance.organization = self.organization


class APPaymentLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = APPaymentLine
        fields = ("invoice", "applied_amount", "discount_taken")
        widgets = {
            "invoice": forms.Select(attrs={"class": "form-select"}),
            "applied_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "discount_taken": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        self.vendor = kwargs.pop("vendor", None)
        super().__init__(*args, **kwargs)

        queryset = PurchaseInvoice.objects.none()
        if self.organization:
            queryset = PurchaseInvoice.objects.filter(organization=self.organization)
        if self.vendor:
            queryset = queryset.filter(vendor=self.vendor)
        self.fields["invoice"].queryset = queryset


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = (
            "code",
            "display_name",
            "legal_name",
            "status",
            "tax_id",
            "payment_term",
            "default_currency",
            "accounts_payable_account",
            "expense_account",
            "agent",
            "area",
            "email",
            "phone_number",
            "website",
            "credit_limit",
            "on_hold",
            "notes",
            "is_active",
        )
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "display_name": forms.TextInput(attrs={"class": "form-control"}),
            "legal_name": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "tax_id": forms.TextInput(attrs={"class": "form-control"}),
            "payment_term": forms.Select(attrs={"class": "form-select"}),
            "default_currency": forms.Select(attrs={"class": "form-select"}),
            "accounts_payable_account": forms.Select(attrs={"class": "form-select"}),
            "expense_account": forms.Select(attrs={"class": "form-select"}),
            "agent": forms.Select(attrs={"class": "form-select"}),
            "area": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "on_hold": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields["payment_term"].queryset = PaymentTerm.objects.filter(
                organization=self.organization,
            ).filter(term_type__in=["ap", "both"])
            self.fields["accounts_payable_account"].queryset = ChartOfAccount.objects.filter(
                organization=self.organization,
            )
            self.fields["expense_account"].queryset = ChartOfAccount.objects.filter(
                organization=self.organization,
            )
            self.fields["agent"].queryset = Agent.objects.filter(
                organization=self.organization,
            )
            self.fields["area"].queryset = LocationNode.objects.filter(
                type=LocationNode.Type.AREA,
                is_active=True,
            )


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            "code",
            "display_name",
            "legal_name",
            "status",
            "tax_id",
            "payment_term",
            "default_currency",
            "accounts_receivable_account",
            "revenue_account",
            "agent",
            "area",
            "email",
            "phone_number",
            "website",
            "credit_limit",
            "credit_rating",
            "credit_review_at",
            "on_credit_hold",
            "notes",
            "is_active",
        )
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "display_name": forms.TextInput(attrs={"class": "form-control"}),
            "legal_name": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "tax_id": forms.TextInput(attrs={"class": "form-control"}),
            "payment_term": forms.Select(attrs={"class": "form-select"}),
            "default_currency": forms.Select(attrs={"class": "form-select"}),
            "accounts_receivable_account": forms.Select(attrs={"class": "form-select"}),
            "revenue_account": forms.Select(attrs={"class": "form-select"}),
            "agent": forms.Select(attrs={"class": "form-select"}),
            "area": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "credit_rating": forms.TextInput(attrs={"class": "form-control"}),
            "credit_review_at": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "on_credit_hold": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields["payment_term"].queryset = PaymentTerm.objects.filter(
                organization=self.organization,
            ).filter(term_type__in=["ar", "both"])
            for field_name in ("accounts_receivable_account", "revenue_account"):
                self.fields[field_name].queryset = ChartOfAccount.objects.filter(
                    organization=self.organization,
                )
            self.fields["agent"].queryset = Agent.objects.filter(
                organization=self.organization,
            )
            self.fields["area"].queryset = LocationNode.objects.filter(
                type=LocationNode.Type.AREA,
                is_active=True,
            )
