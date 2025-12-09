from django import forms

from accounting.forms_mixin import BootstrapFormMixin
from accounting.models import SalesOrder, SalesOrderLine


class SalesOrderForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = (
            "organization",
            "customer",
            "warehouse",
            "order_number",
            "reference_number",
            "order_date",
            "expected_ship_date",
            "currency",
            "exchange_rate",
            "notes",
        )
        widgets = {
            "order_number": forms.TextInput(attrs={"class": "form-control"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control"}),
            "order_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "expected_ship_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "warehouse": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        self.fields["order_number"].required = False
        self.fields["order_number"].widget.attrs.setdefault("placeholder", "Auto-generated")
        self.fields["order_number"].widget.attrs["readonly"] = True
        if self.organization:
            self.fields["customer"].queryset = self.fields["customer"].queryset.filter(
                organization=self.organization,
            )
            self.fields["warehouse"].queryset = self.fields["warehouse"].queryset.filter(
                organization=self.organization,
            )


class SalesOrderLineForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesOrderLine
        fields = (
            "description",
            "product_code",
            "quantity",
            "unit_price",
            "discount_amount",
            "revenue_account",
            "tax_code",
            "tax_amount",
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
        }
