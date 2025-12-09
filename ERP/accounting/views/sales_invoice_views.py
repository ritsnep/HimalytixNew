from decimal import Decimal
import json
from typing import Iterable

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from accounting.forms import SalesInvoiceForm, SalesInvoiceLineForm
from accounting.mixins import PermissionRequiredMixin
from accounting.models import (
    JournalType,
    InvoiceLineTax,
    PaymentTerm,
    SalesInvoice,
    SalesInvoiceLine,
    TaxCode,
)
from accounting.services.sales_invoice_service import SalesInvoiceService
from accounting.services.tax_engine import (
    TaxContext,
    calculate_line_taxes,
    resolve_applicable_taxes,
)
from inventory.models import Product, Warehouse
from usermanagement.models import get_safe_company_config


SalesInvoiceLineFormSet = inlineformset_factory(
    SalesInvoice,
    SalesInvoiceLine,
    form=SalesInvoiceLineForm,
    extra=1,
    can_delete=True,
)


def _get_sales_journal_type(organization):
    """Best-effort lookup for the sales journal type used when posting invoices."""
    if organization is None:
        return None
    candidates = JournalType.objects.filter(organization=organization, is_active=True)
    preferred = candidates.filter(code__iexact="SI").first()
    if preferred:
        return preferred
    named = candidates.filter(Q(name__icontains="sales") | Q(code__icontains="sales")).first()
    return named or candidates.first()


def _tax_fallback_for_region(organization) -> Iterable[TaxCode]:
    """Return a default VAT-like tax code if none is provided and rules are absent."""
    base_currency = getattr(organization, "base_currency_code_id", "") or ""
    vat_query = TaxCode.objects.filter(organization=organization, is_active=True)
    if str(base_currency).upper() in {"NPR", "NRS"}:
        vat = vat_query.filter(Q(code__icontains="VAT") | Q(name__icontains="VAT") | Q(tax_rate__in=[Decimal("13"), Decimal("13.0"), Decimal("13.00")])).order_by("-tax_rate").first()
        if vat:
            return [vat]
    vat = vat_query.order_by("-tax_rate").first()
    return [vat] if vat else []


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
        ).select_related("customer", "currency").order_by("-invoice_date", "-invoice_id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:sales_invoice_create")
        context["create_button_text"] = "New Sales Invoice"
        context.setdefault("page_title", "Sales Invoices")
        return context


class SalesInvoiceCreateView(PermissionRequiredMixin, View):
    template_name = "accounting/sales_invoice_form.html"
    permission_required = ("accounting", "salesinvoice", "add")

    def get(self, request):
        organization = self.get_organization()
        initial_date = timezone.now().date()
        form = SalesInvoiceForm(
            organization=organization,
            initial={"organization": organization, "invoice_date": initial_date},
        )
        formset = SalesInvoiceLineFormSet(prefix="lines", form_kwargs={"organization": organization})
        context = self._build_context(form, formset, organization)
        return render(request, self.template_name, context)

    @transaction.atomic
    def post(self, request):
        organization = self.get_organization()
        form = SalesInvoiceForm(data=request.POST, organization=organization)
        formset = SalesInvoiceLineFormSet(request.POST, prefix="lines", form_kwargs={"organization": organization})
        context = self._build_context(form, formset, organization)
        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        line_payload = []
        invoice_date = form.cleaned_data.get("invoice_date") or timezone.now().date()
        for line_form in formset:
            if not line_form.has_changed() or line_form.cleaned_data.get("DELETE"):
                continue
            data = line_form.cleaned_data
            qty = data.get("quantity") or Decimal("0")
            unit_price = data.get("unit_price") or Decimal("0")
            discount = data.get("discount_amount") or Decimal("0")
            base_amount = (qty * unit_price) - discount
            selected_tax_codes = list(data.get("tax_codes") or [])
            if data.get("tax_code") and data.get("tax_code") not in selected_tax_codes:
                selected_tax_codes.insert(0, data.get("tax_code"))
            tax_total, tax_breakdown, applied_codes = self._calculate_taxes(
                organization=organization,
                invoice_date=invoice_date,
                base_amount=base_amount,
                selected_tax_codes=selected_tax_codes,
            )
            primary_tax = applied_codes[0] if applied_codes else data.get("tax_code")
            line_payload.append(
                {
                    "description": data.get("description"),
                    "product_code": data.get("product_code"),
                    "quantity": qty,
                    "unit_price": unit_price,
                    "discount_amount": discount,
                    "revenue_account": data.get("revenue_account"),
                    "tax_code": primary_tax,
                    "tax_amount": tax_total,
                    "tax_breakdown": tax_breakdown,
                    "metadata": {"applied_tax_codes": [code.code for code in applied_codes]},
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
                invoice_date=invoice_date,
                currency=form.cleaned_data["currency"],
                lines=line_payload,
                payment_term=form.cleaned_data.get("payment_term"),
                due_date=form.cleaned_data.get("due_date"),
                exchange_rate=form.cleaned_data.get("exchange_rate") or Decimal("1"),
                metadata={"source": "ui"},
            )
            invoice.reference_number = form.cleaned_data.get("reference_number") or ""
            invoice.notes = form.cleaned_data.get("notes") or ""
            invoice.warehouse = form.cleaned_data.get("warehouse")
            invoice.save(update_fields=["reference_number", "notes", "warehouse"])

            post_now = request.POST.get("action") == "post"
            if post_now:
                invoice = service.validate_invoice(invoice)
                journal_type = _get_sales_journal_type(organization)
                if journal_type is None:
                    raise ValidationError("Please configure a Sales journal type for this organization.")
                service.post_invoice(
                    invoice,
                    journal_type,
                    warehouse=invoice.warehouse,
                )
                messages.success(request, f"Invoice {invoice.invoice_number} posted and ready to print.")
            else:
                messages.success(request, "Sales invoice saved as draft.")
        except ValidationError as exc:
            transaction.set_rollback(True)
            form.add_error(None, exc)
            return render(request, self.template_name, context)

        return redirect(reverse("accounting:sales_invoice_list"))

    def _calculate_taxes(self, *, organization, invoice_date, base_amount: Decimal, selected_tax_codes):
        codes = [code for code in selected_tax_codes if code]
        if not codes:
            context = TaxContext(
                organization=organization,
                entry_mode="sale",
                transaction_date=invoice_date,
            )
            codes = resolve_applicable_taxes(context)
        if not codes:
            codes = list(_tax_fallback_for_region(organization))
        breakdown = calculate_line_taxes(base_amount, codes, transaction_date=invoice_date) if codes else []
        tax_total = sum(item["tax_amount"] for item in breakdown)
        return tax_total, breakdown, codes

    def _build_context(self, form, formset, organization):
        return {
            "form": form,
            "line_formset": formset,
            "formset": formset,
            "form_title": "New Sales Invoice",
            "back_url": "accounting:sales_invoice_list",
            "product_data_json": json.dumps(self._serialize_products(organization), default=str),
            "tax_code_data_json": json.dumps(self._serialize_tax_codes(organization), default=str),
            "customer_data_json": json.dumps(self._serialize_customers(form), default=str),
            "payment_term_data_json": json.dumps(self._serialize_payment_terms(organization), default=str),
        }

    def _serialize_products(self, organization):
        products = Product.objects.filter(organization=organization).select_related("income_account")
        return [
            {
                "code": product.code,
                "name": product.name,
                "price": str(product.sale_price or Decimal("0")),
                "revenue_account": product.income_account_id,
                "is_inventory_item": product.is_inventory_item,
            }
            for product in products
        ]

    def _serialize_tax_codes(self, organization):
        tax_codes = TaxCode.objects.filter(organization=organization, is_active=True).select_related("sales_account")
        return [
            {
                "id": tax.tax_code_id,
                "code": tax.code,
                "name": tax.name,
                "rate": str(tax.tax_rate or tax.rate or Decimal("0")),
                "is_compound": tax.is_compound,
                "sales_account": tax.sales_account_id,
            }
            for tax in tax_codes
        ]

    def _serialize_customers(self, form):
        qs = form.fields["customer"].queryset
        return [
            {
                "id": customer.pk,
                "name": customer.display_name,
                "payment_term": customer.payment_term_id,
                "currency": customer.default_currency_id,
                "tax_id": customer.tax_id,
                "revenue_account": customer.revenue_account_id,
            }
            for customer in qs
        ]

    def _serialize_payment_terms(self, organization):
        terms = PaymentTerm.objects.filter(
            organization=organization,
            term_type__in=["ar", "both"],
            is_active=True,
        )
        return [
            {
                "id": term.pk,
                "name": term.name,
                "net_due_days": term.net_due_days,
            }
            for term in terms
        ]


class SalesInvoicePostView(PermissionRequiredMixin, View):
    permission_required = ("accounting", "salesinvoice", "post")

    @transaction.atomic
    def post(self, request, invoice_id):
        organization = self.get_organization()
        invoice = get_object_or_404(
            SalesInvoice.objects.select_related("customer"),
            invoice_id=invoice_id,
            organization=organization,
        )
        service = SalesInvoiceService(request.user)
        warehouse = invoice.warehouse
        warehouse_id = request.POST.get("warehouse_id")
        if warehouse_id:
            warehouse = get_object_or_404(Warehouse, pk=warehouse_id, organization=organization)
            if invoice.warehouse_id != warehouse.pk:
                invoice.warehouse = warehouse
                invoice.save(update_fields=["warehouse"])

        try:
            invoice = service.validate_invoice(invoice)
            journal_type = _get_sales_journal_type(organization)
            if journal_type is None:
                raise ValidationError("Please configure a Sales journal type for this organization.")
            service.post_invoice(invoice, journal_type, warehouse=warehouse)
            messages.success(request, f"Invoice {invoice.invoice_number} posted successfully.")
        except ValidationError as exc:
            messages.error(request, f"Unable to post invoice: {exc}")
        return redirect(reverse("accounting:sales_invoice_list"))


class SalesInvoicePrintView(PermissionRequiredMixin, DetailView):
    model = SalesInvoice
    context_object_name = "invoice"
    permission_required = ("accounting", "salesinvoice", "view")
    pk_url_kwarg = "invoice_id"

    def get_queryset(self):
        organization = self.get_organization()
        return SalesInvoice.objects.filter(organization=organization).select_related(
            "customer",
            "currency",
            "payment_term",
            "organization",
        )

    def get_template_names(self):
        template_key = self._template_key()
        if template_key == "thermal":
            return ["accounting/print/sales_invoice_thermal.html"]
        return ["accounting/print/sales_invoice_a4.html"]

    def _template_key(self):
        config = self._company_config()
        return getattr(config, "invoice_template", None) or "a4"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object
        content_type = ContentType.objects.get_for_model(SalesInvoiceLine)
        tax_rows = (
            InvoiceLineTax.objects.filter(
                content_type=content_type,
                object_id__in=list(invoice.lines.values_list("pk", flat=True)),
            )
            .select_related("tax_code")
            .order_by("sequence")
        )
        tax_map = {}
        for row in tax_rows:
            tax_map.setdefault(row.object_id, []).append(
                {
                    "code": row.tax_code.code if row.tax_code else "",
                    "name": row.tax_code.name if row.tax_code else "",
                    "amount": row.tax_amount,
                }
            )
        organization = self.get_organization()
        context.update(
            {
                "lines": invoice.lines.select_related("revenue_account", "tax_code").order_by("line_number"),
                "tax_breakdown": tax_map,
                "organization": organization,
                "invoice_logo_url": getattr(self._company_config(), "invoice_logo_url", ""),
                "template_key": self._template_key(),
            }
        )
        return context

    def _company_config(self):
        if not hasattr(self, "_company_config_cache"):
            self._company_config_cache = get_safe_company_config(self.get_organization())
        return self._company_config_cache
