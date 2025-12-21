from __future__ import annotations

from decimal import Decimal

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from inventory.models import Product, Warehouse
from accounting.models import ChartOfAccount, Currency, Vendor
from purchasing.models import (
    LandedCostDocument,
    LandedCostLine,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
)
from utils.widgets import dual_date_widget, set_default_date_initial


class OrganizationBoundFormMixin:
    """Filters queryset-backed fields by organization when provided."""

    organization_bound_fields: tuple[str, ...] = ()

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if organization:
            self._restrict_querysets(organization)
        self._apply_dual_calendar_widgets()

    def _restrict_querysets(self, organization):  # pragma: no cover - override hook
        return

    def _apply_dual_calendar_widgets(self):
        for name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                attrs = dict(getattr(field.widget, "attrs", {}) or {})
                field.widget = dual_date_widget(attrs=attrs, organization=self.organization)
                set_default_date_initial(self, name, field)


class PurchaseInvoiceForm(OrganizationBoundFormMixin, forms.ModelForm):
    invoice_date = forms.DateField(widget=dual_date_widget())
    due_date = forms.DateField(
        widget=dual_date_widget(),
        required=False,
    )

    class Meta:
        model = PurchaseInvoice
        fields = [
            "vendor",
            "invoice_number",
            "invoice_date",
            "due_date",
            "currency",
            "exchange_rate",
        ]
        widgets = {
            "invoice_number": forms.TextInput(attrs={"placeholder": "Auto if left blank"}),
            "exchange_rate": forms.NumberInput(attrs={"step": "0.000001"}),
        }

    def _restrict_querysets(self, organization):
        self.fields["vendor"].queryset = (
            Vendor.objects.filter(organization=organization, is_active=True)
            .order_by("display_name")
        )
        base_currency = None
        if organization.base_currency_code:
            base_currency = Currency.objects.filter(
                currency_code=organization.base_currency_code
            ).first()
        if base_currency and not self.initial.get("currency") and not self.instance.pk:
            self.initial["currency"] = base_currency


class PurchaseInvoiceLineForm(OrganizationBoundFormMixin, forms.ModelForm):
    quantity = forms.DecimalField(min_value=Decimal("0.0001"), max_digits=18, decimal_places=4)
    unit_cost = forms.DecimalField(min_value=Decimal("0.0000"), max_digits=18, decimal_places=4, label="Unit Price")
    vat_rate = forms.DecimalField(min_value=Decimal("0"), max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = PurchaseInvoiceLine
        fields = [
            "product",
            "warehouse",
            "description",
            "quantity",
            "unit_cost",
            "vat_rate",
            "account",
            "input_vat_account",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Optional line memo"}),
        }

    def _restrict_querysets(self, organization):
        self.fields["product"].queryset = (
            Product.objects.filter(organization=organization).order_by("name")
        )
        self.fields["warehouse"].queryset = (
            Warehouse.objects.filter(organization=organization, is_active=True)
            .order_by("name")
        )
        account_qs = ChartOfAccount.objects.filter(organization=organization).order_by("account_name")
        self.fields["account"].queryset = account_qs
        self.fields["input_vat_account"].queryset = account_qs


class BasePurchaseInvoiceLineFormSet(BaseInlineFormSet):
    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["organization"] = self.organization
        return super()._construct_form(i, **kwargs)


PurchaseInvoiceLineFormSet = inlineformset_factory(
    PurchaseInvoice,
    PurchaseInvoiceLine,
    form=PurchaseInvoiceLineForm,
    formset=BasePurchaseInvoiceLineFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class LandedCostDocumentForm(forms.ModelForm):
    document_date = forms.DateField(widget=dual_date_widget())

    class Meta:
        model = LandedCostDocument
        fields = ["document_date", "basis", "note"]
        widgets = {
            "note": forms.TextInput(attrs={"placeholder": "Optional memo"})
        }


class LandedCostLineForm(OrganizationBoundFormMixin, forms.ModelForm):
    amount = forms.DecimalField(min_value=Decimal("0.01"), max_digits=18, decimal_places=2)

    class Meta:
        model = LandedCostLine
        fields = ["description", "amount", "credit_account"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Freight / Insurance / Duty"}),
        }

    def _restrict_querysets(self, organization):
        self.fields["credit_account"].queryset = ChartOfAccount.objects.filter(
            organization=organization
        ).order_by("account_name")


class BaseLandedCostLineFormSet(BaseInlineFormSet):
    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["organization"] = self.organization
        return super()._construct_form(i, **kwargs)


LandedCostLineFormSet = inlineformset_factory(
    LandedCostDocument,
    LandedCostLine,
    form=LandedCostLineForm,
    formset=BaseLandedCostLineFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# Purchase Order Forms
class PurchaseOrderForm(OrganizationBoundFormMixin, forms.ModelForm):
    """Form for creating/editing purchase orders."""
    
    order_date = forms.DateField(widget=dual_date_widget())
    due_date = forms.DateField(
        widget=dual_date_widget(),
        required=False,
    )

    class Meta:
        model = PurchaseOrder
        fields = [
            "vendor",
            "order_date",
            "due_date",
            "currency",
            "exchange_rate",
            "notes",
        ]
        widgets = {
            "exchange_rate": forms.NumberInput(attrs={"step": "0.000001"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Additional notes"}),
        }

    def _restrict_querysets(self, organization):
        """Restrict vendor queryset to organization."""
        self.fields["vendor"].queryset = (
            Vendor.objects.filter(organization=organization, is_active=True)
            .order_by("display_name")
        )
        
        # Set default currency to base currency
        if organization.base_currency_code:
            base_currency = Currency.objects.filter(
                currency_code=organization.base_currency_code
            ).first()
            if base_currency and not self.initial.get("currency") and not self.instance.pk:
                self.initial["currency"] = base_currency


class PurchaseOrderLineForm(OrganizationBoundFormMixin, forms.ModelForm):
    """Form for adding/editing PO line items."""
    
    quantity_ordered = forms.DecimalField(
        min_value=Decimal("0.0001"),
        max_digits=18,
        decimal_places=4,
    )
    unit_price = forms.DecimalField(
        min_value=Decimal("0.0000"),
        max_digits=18,
        decimal_places=4,
    )
    vat_rate = forms.DecimalField(
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=Decimal("0"),
    )

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "product",
            "quantity_ordered",
            "unit_price",
            "vat_rate",
            "expected_delivery_date",
            "inventory_account",
            "expense_account",
        ]
        widgets = {
            "expected_delivery_date": dual_date_widget(),
        }

    def _restrict_querysets(self, organization):
        """Restrict querysets to organization."""
        self.fields["product"].queryset = (
            Product.objects.filter(organization=organization)
            .order_by("name")
        )
        
        account_qs = ChartOfAccount.objects.filter(
            organization=organization
        ).order_by("account_name")
        self.fields["inventory_account"].queryset = account_qs
        self.fields["expense_account"].queryset = account_qs


class BasePurchaseOrderLineFormSet(BaseInlineFormSet):
    """Formset for handling multiple PO line items."""
    
    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["organization"] = self.organization
        return super()._construct_form(i, **kwargs)


PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    formset=BasePurchaseOrderLineFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# Goods Receipt Forms
class GoodsReceiptForm(OrganizationBoundFormMixin, forms.ModelForm):
    """Form for creating/editing goods receipts."""
    
    receipt_date = forms.DateField(widget=dual_date_widget())

    class Meta:
        model = GoodsReceipt
        fields = [
            "purchase_order",
            "warehouse",
            "receipt_date",
            "reference_number",
            "notes",
        ]
        widgets = {
            "reference_number": forms.TextInput(attrs={"placeholder": "Carrier/awb reference"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "QC notes, damage, etc"}),
        }

    def _restrict_querysets(self, organization):
        """Restrict querysets to organization."""
        from purchasing.models import PurchaseOrder
        
        # Only show POs in SENT status ready for receiving
        self.fields["purchase_order"].queryset = (
            PurchaseOrder.objects
            .filter(organization=organization, status=PurchaseOrder.Status.SENT)
            .order_by("-created_at")
        )
        
        self.fields["warehouse"].queryset = (
            Warehouse.objects.filter(organization=organization, is_active=True)
            .order_by("name")
        )


class GoodsReceiptLineForm(OrganizationBoundFormMixin, forms.ModelForm):
    """Form for editing GR line items (quantities received/accepted)."""
    
    quantity_received = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=18,
        decimal_places=4,
    )
    quantity_accepted = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=18,
        decimal_places=4,
    )
    quantity_rejected = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=18,
        decimal_places=4,
        required=False,
        initial=Decimal("0"),
    )

    class Meta:
        model = GoodsReceiptLine
        fields = [
            "quantity_received",
            "quantity_accepted",
            "quantity_rejected",
            "qc_result",
            "batch_number",
            "expiry_date",
            "serial_numbers",
            "notes",
        ]
        widgets = {
            "expiry_date": dual_date_widget(),
            "serial_numbers": forms.TextInput(attrs={"placeholder": "Comma-separated"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "QC notes"}),
        }


class BaseGoodsReceiptLineFormSet(BaseInlineFormSet):
    """Formset for handling multiple GR line items."""
    
    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["organization"] = self.organization
        return super()._construct_form(i, **kwargs)


GoodsReceiptLineFormSet = inlineformset_factory(
    GoodsReceipt,
    GoodsReceiptLine,
    form=GoodsReceiptLineForm,
    formset=BaseGoodsReceiptLineFormSet,
    extra=0,  # Don't add empty lines - pre-filled from PO
    can_delete=False,  # Don't delete once created
    validate_min=False,
)
