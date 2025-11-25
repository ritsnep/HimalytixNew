from django import forms
from django.utils import timezone

from lpg_vertical.models import (
    ConversionRule,
    CylinderSKU,
    CylinderType,
    Dealer,
    LpgProduct,
    LogisticsTrip,
    NocPurchase,
    SalesInvoice,
    TransportProvider,
    Vehicle,
)


class OrganizationModelForm(forms.ModelForm):
    """Base form that stamps the organization on save and filters related fields."""

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if hasattr(field, "queryset") and field.queryset is not None:
                field.queryset = field.queryset.filter(organization=self.organization)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance


class CylinderTypeForm(OrganizationModelForm):
    class Meta:
        model = CylinderType
        fields = ["name", "kg_per_cylinder", "is_active"]


class CylinderSKUForm(OrganizationModelForm):
    class Meta:
        model = CylinderSKU
        fields = ["name", "cylinder_type", "state", "code", "is_active"]


class DealerForm(OrganizationModelForm):
    class Meta:
        model = Dealer
        fields = ["company_code", "name", "contact_person", "phone", "address", "tax_id", "credit_limit", "active"]


class TransportProviderForm(OrganizationModelForm):
    class Meta:
        model = TransportProvider
        fields = ["name", "contact"]


class VehicleForm(OrganizationModelForm):
    class Meta:
        model = Vehicle
        fields = ["number", "provider", "capacity"]


class ConversionRuleForm(OrganizationModelForm):
    class Meta:
        model = ConversionRule
        fields = ["cylinder_type", "mt_fraction_per_cylinder", "is_default"]


class LpgProductForm(OrganizationModelForm):
    class Meta:
        model = LpgProduct
        fields = ["code", "name", "description", "is_bulk", "is_active"]


class NocPurchaseForm(OrganizationModelForm):
    class Meta:
        model = NocPurchase
        fields = [
            "bill_no",
            "date",
            "quantity_mt",
            "rate_per_mt",
            "transport_cost",
            "tax_amount",
            "receipt_location",
        ]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("date"):
            self.initial["date"] = timezone.now().date()


class SalesInvoiceForm(OrganizationModelForm):
    class Meta:
        model = SalesInvoice
        fields = [
            "invoice_no",
            "date",
            "dealer",
            "payment_type",
            "empty_cylinders_collected",
            "notes",
        ]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class LogisticsTripForm(OrganizationModelForm):
    class Meta:
        model = LogisticsTrip
        fields = [
            "date",
            "provider",
            "vehicle",
            "cylinder_sku",
            "from_location",
            "to_location",
            "cylinder_count",
            "cost",
            "ref_doc_type",
            "ref_doc_id",
            "notes",
        ]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
