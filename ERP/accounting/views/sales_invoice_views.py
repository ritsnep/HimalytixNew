from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView

from accounting.forms import SalesInvoiceForm, SalesInvoiceLineForm
from accounting.mixins import PermissionRequiredMixin
from accounting.models import SalesInvoice, SalesInvoiceLine
from accounting.services.sales_invoice_service import SalesInvoiceService


SalesInvoiceLineFormSet = inlineformset_factory(
    SalesInvoice,
    SalesInvoiceLine,
    form=SalesInvoiceLineForm,
    extra=1,
    can_delete=True,
)


class SalesInvoiceListView(PermissionRequiredMixin, ListView):
    model = SalesInvoice
    template_name = "accounting/sales_invoice_list.html"
    context_object_name = "invoices"
    permission_required = ("accounting", "salesinvoice", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return SalesInvoice.objects.none()
        return SalesInvoice.objects.filter(
            organization=organization
        ).select_related("customer").order_by("-invoice_date", "-invoice_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:sales_invoice_create")
        context["create_button_text"] = "New Sales Invoice"
        return context


class SalesInvoiceCreateView(PermissionRequiredMixin, View):
    template_name = "accounting/sales_invoice_form.html"
    permission_required = ("accounting", "salesinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        form = SalesInvoiceForm(organization=organization, initial={'organization': organization})
        formset = SalesInvoiceLineFormSet(prefix="lines")
        context = self._build_context(form, formset)
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        form = SalesInvoiceForm(data=request.POST, organization=organization)
        formset = SalesInvoiceLineFormSet(request.POST, prefix="lines")
        context = self._build_context(form, formset)
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        line_payload = []
        for line_form in formset:
            if not line_form.has_changed() or line_form.cleaned_data.get("DELETE"):
                continue
            data = line_form.cleaned_data
            line_payload.append(
                {
                    "description": data.get("description"),
                    "product_code": data.get("product_code"),
                    "quantity": data.get("quantity"),
                    "unit_price": data.get("unit_price"),
                    "discount_amount": data.get("discount_amount"),
                    "revenue_account": data.get("revenue_account"),
                    "tax_code": data.get("tax_code"),
                    "tax_amount": data.get("tax_amount"),
                    "cost_center": data.get("cost_center"),
                    "department": data.get("department"),
                    "project": data.get("project"),
                    "dimension_value": data.get("dimension_value"),
                }
            )

        if not line_payload:
            form.add_error(None, "At least one line item is required.")
            return render(request, self.template_name, context)

        try:
            service = SalesInvoiceService(request.user)
            invoice = service.create_invoice(
                organization=organization,
                customer=form.cleaned_data["customer"],
                invoice_number=form.cleaned_data["invoice_number"],
                invoice_date=form.cleaned_data["invoice_date"],
                currency=form.cleaned_data["currency"],
                lines=line_payload,
                payment_term=form.cleaned_data.get("payment_term"),
                due_date=form.cleaned_data.get("due_date"),
                exchange_rate=form.cleaned_data.get("exchange_rate") or Decimal("1"),
                metadata={},
            )
            invoice.reference_number = form.cleaned_data.get("reference_number") or ""
            invoice.notes = form.cleaned_data.get("notes") or ""
            invoice.warehouse = form.cleaned_data.get("warehouse")
            invoice.save(update_fields=["reference_number", "notes", "warehouse"])
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, self.template_name, context)

        messages.success(request, "Sales invoice saved as draft.")
        return redirect(reverse("accounting:sales_invoice_list"))

    def _build_context(self, form, formset):
        return {
            "form": form,
            "line_formset": formset,
            "formset": formset,
            "form_title": "New Sales Invoice",
            "back_url": "accounting:sales_invoice_list",
        }
