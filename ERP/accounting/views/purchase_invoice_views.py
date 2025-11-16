from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from accounting.forms import PurchaseInvoiceForm, PurchaseInvoiceLineForm
from accounting.models import Vendor
from accounting.services.purchase_invoice_service import PurchaseInvoiceService
from accounting.views.views_mixins import AccountsPayablePermissionMixin

PurchaseInvoiceLineFormSet = forms.formset_factory(
    PurchaseInvoiceLineForm,
    extra=1,
    can_delete=True,
)


class VendorBillCreateView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/vendor_bill_form.html"
    permission_tuple = ("accounting", "purchaseinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        context = self._build_context(
            organization,
            PurchaseInvoiceForm(organization=organization, initial={'organization': organization}),
            self._build_line_formset(organization),
        )
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        form = PurchaseInvoiceForm(data=request.POST, organization=organization)
        line_formset = self._build_line_formset(organization, data=request.POST)
        context = self._build_context(organization, form, line_formset)
        if not (form.is_valid() and line_formset.is_valid()):
            return render(request, self.template_name, context)

        lines = []
        for line_form in line_formset:
            if not line_form.has_changed() or line_form.cleaned_data.get("DELETE"):
                continue
            data = line_form.cleaned_data
            lines.append(
                {
                    "description": data.get("description"),
                    "product_code": data.get("product_code"),
                    "quantity": data.get("quantity"),
                    "unit_cost": data.get("unit_cost"),
                    "discount_amount": data.get("discount_amount"),
                    "account": data.get("account"),
                    "tax_code": data.get("tax_code"),
                    "tax_amount": data.get("tax_amount"),
                    "cost_center": data.get("cost_center"),
                    "department": data.get("department"),
                    "project": data.get("project"),
                    "dimension_value": data.get("dimension_value"),
                    "po_reference": data.get("po_reference"),
                    "receipt_reference": data.get("receipt_reference"),
                }
            )

        if not lines:
            form.add_error(None, "At least one line item is required.")
            return render(request, self.template_name, context)

        try:
            service = PurchaseInvoiceService(request.user)
            invoice = service.create_invoice(
                organization=organization,
                vendor=form.cleaned_data["vendor"],
                invoice_number=form.cleaned_data["invoice_number"],
                invoice_date=form.cleaned_data["invoice_date"],
                currency=form.cleaned_data["currency"],
                exchange_rate=form.cleaned_data.get("exchange_rate") or Decimal("1"),
                lines=lines,
                payment_term=form.cleaned_data.get("payment_term"),
                due_date=form.cleaned_data.get("due_date"),
                metadata={},
            )
            invoice.external_reference = form.cleaned_data.get("external_reference") or ""
            invoice.po_number = form.cleaned_data.get("po_number") or ""
            invoice.receipt_reference = form.cleaned_data.get("receipt_reference") or ""
            invoice.notes = form.cleaned_data.get("notes") or ""
            invoice.save(
                update_fields=["external_reference", "po_number", "receipt_reference", "notes"]
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, self.template_name, context)

        messages.success(request, "Vendor bill saved as draft.")
        return redirect(reverse("accounting:vendor_bill_create"))

    def _build_line_formset(self, organization, data=None):
        kwargs = {"prefix": "lines", "form_kwargs": {"organization": organization}}
        if data is not None:
            kwargs["data"] = data
        return PurchaseInvoiceLineFormSet(**kwargs)

    def _build_context(self, organization, form, line_formset):
        return {
            "form": form,
            "line_formset": line_formset,
            "line_row_url": reverse("accounting:vendor_bill_line_row"),
            "vendor_summary_url": reverse("accounting:vendor_summary_hx"),
            "organization": organization,
        }


class VendorBillLineRowView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/partials/purchase_invoice_line_row.html"
    permission_tuple = ("accounting", "purchaseinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        index = request.GET.get("index", "0")
        try:
            int_index = int(index)
        except ValueError:
            int_index = 0
        prefix = f"lines-{int_index}"
        form = PurchaseInvoiceLineForm(prefix=prefix, organization=organization)
        return render(request, self.template_name, {"form": form})


class VendorSummaryHXView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/partials/vendor_summary.html"
    permission_tuple = ("accounting", "purchaseinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        vendor_id = request.GET.get("vendor")
        vendor = None
        if vendor_id:
            try:
                vendor = Vendor.objects.get(pk=vendor_id, organization=organization)
            except Vendor.DoesNotExist:
                vendor = None
        return render(request, self.template_name, {"vendor": vendor})
