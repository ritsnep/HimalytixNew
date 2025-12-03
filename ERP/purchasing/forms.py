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
)


class OrganizationBoundFormMixin:
    """Filters queryset-backed fields by organization when provided."""

    organization_bound_fields: tuple[str, ...] = ()

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if organization:
            self._restrict_querysets(organization)

    def _restrict_querysets(self, organization):  # pragma: no cover - override hook
        return


class PurchaseInvoiceForm(OrganizationBoundFormMixin, forms.ModelForm):
    invoice_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        required=False,
    )

    class Meta:
        model = PurchaseInvoice
        fields = [
            "supplier",
            "number",
            "invoice_date",
            "due_date",
            "currency",
            "exchange_rate",
        ]
        widgets = {
            "number": forms.TextInput(attrs={"placeholder": "Auto if left blank"}),
            "exchange_rate": forms.NumberInput(attrs={"step": "0.000001"}),
        }

    def _restrict_querysets(self, organization):
        self.fields["supplier"].queryset = (
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
    unit_price = forms.DecimalField(min_value=Decimal("0.0000"), max_digits=18, decimal_places=4)
    vat_rate = forms.DecimalField(min_value=Decimal("0"), max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = PurchaseInvoiceLine
        fields = [
            "product",
            "warehouse",
            "description",
            "quantity",
            "unit_price",
            "vat_rate",
            "expense_account",
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
        self.fields["expense_account"].queryset = account_qs
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
    document_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

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
        fields = ["description", "amount", "gl_account"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Freight / Insurance / Duty"}),
        }

    def _restrict_querysets(self, organization):
        self.fields["gl_account"].queryset = ChartOfAccount.objects.filter(
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
