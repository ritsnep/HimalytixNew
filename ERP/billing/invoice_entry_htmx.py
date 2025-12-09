
"""
Sales Invoice Entry Views with HTMX
Interactive invoice creation with real-time calculations and customer search.
"""
import logging
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST
from weasyprint import HTML

from accounting.ird_service import record_invoice_print
from accounting.models import (
    ChartOfAccount,
    Currency,
    Customer,
    DocumentSequenceConfig,
    FiscalYear,
    InvoiceLineTax,
    JournalType,
    PaymentTerm,
    SalesInvoice,
    SalesInvoiceLine,
    TaxCode,
)
from accounting.services.ird_submission_service import IRDSubmissionService
from accounting.services.sales_invoice_service import SalesInvoiceService
from accounting.services.tax_engine import calculate_line_taxes
from inventory.models import Product, Warehouse
from utils.branding import get_branding_from_request
from usermanagement.models import get_safe_company_config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_active_org(request):
    """Prefer the active organization helper and fall back to the direct FK."""
    getter = getattr(request.user, "get_active_organization", None)
    if callable(getter):
        org = getter()
        if org:
            return org
    return getattr(request.user, "organization", None)


def _preview_invoice_number(organization, invoice_date):
    """Peek at the next invoice number without incrementing the sequence."""
    if not organization:
        return ""
    invoice_date = invoice_date or timezone.now().date()
    sequence = DocumentSequenceConfig.get_or_create_sequence(
        organization=organization, document_type="sales_invoice"
    )
    fiscal_year = None
    if sequence.reset_policy == "fiscal_year" or sequence.fiscal_year_prefix:
        fiscal_year = FiscalYear.get_for_date(organization, invoice_date)

    next_value = sequence.sequence_next or 1
    if (
        fiscal_year
        and sequence.reset_policy == "fiscal_year"
        and sequence.last_sequence_fiscal_year_id != fiscal_year.pk
    ):
        next_value = 1

    prefix_parts = []
    if sequence.fiscal_year_prefix and fiscal_year:
        prefix_parts.append(fiscal_year.code)
    if sequence.prefix:
        prefix_parts.append(sequence.prefix)
    prefix = "".join(prefix_parts)
    suffix = sequence.suffix or ""

    return f"{prefix}{str(next_value).zfill(sequence.sequence_padding or 1)}{suffix}"


def _gather_tax_breakdown(base_amount, tax_code_ids, organization, invoice_date):
    """Calculate multi-tax breakdown and return (total, breakdown list, codes)."""
    codes = list(
        TaxCode.objects.filter(
            organization=organization, tax_code_id__in=tax_code_ids, is_active=True
        )
    )
    breakdown = calculate_line_taxes(base_amount, codes, transaction_date=invoice_date)
    total_tax = sum((entry["tax_amount"] for entry in breakdown), Decimal("0"))
    return total_tax, breakdown, codes


def _aggregate_tax_summary(entries):
    """Aggregate a list of breakdown entries to a code->total mapping."""
    summary = {}
    for entry in entries:
        code = entry["tax_code"]
        summary.setdefault(
            code.tax_code_id,
            {"code": code.code, "name": code.name, "amount": Decimal("0")},
        )
        summary[code.tax_code_id]["amount"] += entry["tax_amount"]
    return summary.values()


def _tax_lines_for_invoice(invoice):
    """Fetch invoice line tax breakdowns for print/detail rendering."""
    content_type = ContentType.objects.get_for_model(SalesInvoiceLine)
    taxes = (
        InvoiceLineTax.objects.filter(
            content_type=content_type,
            object_id__in=invoice.lines.values_list("pk", flat=True),
        )
        .select_related("tax_code")
        .order_by("object_id", "sequence")
    )
    summary_entries = [
        {"tax_code": t.tax_code, "tax_amount": t.tax_amount} for t in taxes
    ]
    return taxes, _aggregate_tax_summary(summary_entries)


def _resolve_template_style(request, organization):
    """Resolve invoice print template style respecting org setting and overrides."""
    allowed = {"a4", "thermal"}
    override = (request.GET.get("template") or "").lower()
    if override in allowed:
        return override
    config = get_safe_company_config(organization)
    org_template = getattr(config, "invoice_template", None)
    if org_template in allowed:
        return org_template
    return getattr(settings, "INVOICE_DEFAULT_TEMPLATE", "a4")


# ---------------------------------------------------------------------------
# Entry & lookup endpoints
# ---------------------------------------------------------------------------
@login_required
def invoice_create(request):
    """Main invoice creation page"""
    organization = _get_active_org(request)
    invoice_date = date.today()

    revenue_accounts = ChartOfAccount.objects.filter(
        organization=organization,
        account_type__nature="income",
        is_active=True,
    ).order_by("account_name")

    tax_rates = TaxCode.objects.filter(
        organization=organization,
        is_active=True,
    ).order_by("rate")

    currencies = Currency.objects.filter(is_active=True).order_by("currency_code")
    default_currency = getattr(organization, "base_currency_code", None) or currencies.first()

    payment_terms = PaymentTerm.objects.filter(
        organization=organization,
        is_active=True,
        term_type__in=["ar", "both"],
    ).order_by("name")

    journal_types = JournalType.objects.filter(
        organization=organization, is_active=True
    ).order_by("name")

    warehouses = Warehouse.objects.filter(
        organization=organization, is_active=True
    ).order_by("name")

    context = {
        "revenue_accounts": revenue_accounts,
        "tax_rates": tax_rates,
        "tax_codes": tax_rates,
        "currencies": currencies,
        "default_currency": default_currency,
        "currency_code": default_currency.currency_code if default_currency else "NPR",
        "payment_terms": payment_terms,
        "journal_types": journal_types,
        "warehouses": warehouses,
        "today": invoice_date,
        "next_invoice_number": _preview_invoice_number(organization, invoice_date),
    }

    return render(request, "billing/invoice_create.html", context)


@login_required
def customer_search(request):
    """HTMX endpoint: Search customers as user types"""
    query = request.GET.get("q", "").strip()
    organization = _get_active_org(request)

    if len(query) < 2:
        return HttpResponse("")

    customers = Customer.objects.filter(
        organization=organization,
        is_active=True,
    ).filter(
        Q(display_name__icontains=query)
        | Q(legal_name__icontains=query)
        | Q(phone_number__icontains=query)
        | Q(tax_id__icontains=query)
    )[:10]

    return render(request, "billing/partials/customer_results.html", {"customers": customers})


@login_required
def product_search(request):
    """HTMX endpoint: Search products for invoice line"""
    query = request.GET.get("q", "").strip()
    if not query:
        for key, value in request.GET.items():
            if key.startswith("description_") and value.strip():
                query = value.strip()
                break
    organization = _get_active_org(request)
    line_index = request.GET.get("line_index", "")

    if len(query) < 2:
        return HttpResponse("")

    products = Product.objects.select_related("income_account").filter(
        organization=organization,
        is_active=True,
    ).filter(Q(name__icontains=query) | Q(code__icontains=query))[:10]

    return render(
        request,
        "billing/partials/product_results.html",
        {"products": products, "line_index": line_index},
    )


@login_required
def add_invoice_line(request):
    """HTMX endpoint: Add new invoice line row"""
    line_index = request.GET.get("index", 1)
    organization = _get_active_org(request)

    revenue_accounts = ChartOfAccount.objects.filter(
        organization=organization,
        account_type__nature="income",
        is_active=True,
    )

    tax_rates = TaxCode.objects.filter(
        organization=organization,
        is_active=True,
    ).order_by("rate")

    return render(
        request,
        "billing/partials/invoice_line_row.html",
        {
            "line_index": line_index,
            "revenue_accounts": revenue_accounts,
            "tax_rates": tax_rates,
        },
    )


@login_required
def calculate_line_total(request):
    """HTMX endpoint: Calculate line total when quantity/price changes"""
    quantity = Decimal(request.POST.get("quantity", 0))
    unit_price = Decimal(request.POST.get("unit_price", 0))
    tax_code_ids = request.POST.getlist("tax_codes") or []
    invoice_date = timezone.now().date()
    line_index = request.POST.get("line_index", 0)

    line_subtotal = quantity * unit_price
    tax_amount, breakdown, _ = _gather_tax_breakdown(
        line_subtotal, tax_code_ids, _get_active_org(request), invoice_date
    )
    line_total = line_subtotal + tax_amount

    return render(
        request,
        "billing/partials/line_total_display.html",
        {
            "line_index": line_index,
            "line_subtotal": line_subtotal,
            "tax_amount": tax_amount,
            "line_total": line_total,
            "tax_breakdown": breakdown,
        },
    )


@login_required
def calculate_invoice_total(request):
    """HTMX endpoint: Recalculate invoice totals"""
    line_indices = request.POST.getlist("line_index[]")
    try:
        invoice_date = datetime.fromisoformat(request.POST.get("invoice_date") or "").date()
    except Exception:
        invoice_date = date.today()

    subtotal = Decimal(0)
    tax_total = Decimal(0)
    breakdown_entries = []
    currency_code = request.POST.get("currency") or getattr(
        _get_active_org(request), "base_currency_code_id", "NPR"
    )

    for idx in line_indices:
        quantity = Decimal(request.POST.get(f"quantity_{idx}", 0) or 0)
        unit_price = Decimal(request.POST.get(f"unit_price_{idx}", 0) or 0)
        tax_code_ids = request.POST.getlist(f"tax_codes_{idx}") or []
        line_subtotal = quantity * unit_price

        discount_percent = Decimal(request.POST.get("discount_percent", 0) or 0)
        discount_amount = (
            (line_subtotal * discount_percent / Decimal("100")).quantize(Decimal("0.01"))
            if discount_percent
            else Decimal("0")
        )
        net_base = line_subtotal - discount_amount

        line_tax, breakdown, _ = _gather_tax_breakdown(
            net_base, tax_code_ids, _get_active_org(request), invoice_date
        )

        subtotal += line_subtotal
        tax_total += line_tax
        breakdown_entries.extend(breakdown)

    discount_percent = Decimal(request.POST.get("discount_percent", 0) or 0)
    discount_amount = (subtotal * discount_percent) / 100
    total = subtotal - discount_amount + tax_total

    return render(
        request,
        "billing/partials/invoice_totals.html",
        {
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "tax_total": tax_total,
            "total": total,
            "tax_breakdown": _aggregate_tax_summary(breakdown_entries),
            "currency_code": currency_code,
        },
    )


# ---------------------------------------------------------------------------
# Persistence / lifecycle
# ---------------------------------------------------------------------------
@login_required
def invoice_save(request):
    """Save invoice (draft or posted)"""
    if request.method != "POST":
        return redirect("invoice_create")

    organization = _get_active_org(request)
    action = request.POST.get("action", "save_draft")

    customer_id = request.POST.get("customer_id")
    if not customer_id:
        messages.error(request, "Select a customer before saving the invoice.")
        return redirect("billing:invoice_create")

    try:
        customer = Customer.objects.get(pk=customer_id, organization=organization)
    except Customer.DoesNotExist:
        messages.error(request, "Invalid customer selected.")
        return redirect("billing:invoice_create")

    try:
        invoice_date = datetime.fromisoformat(request.POST.get("invoice_date")).date()
    except Exception:
        messages.error(request, "Invoice date is required.")
        return redirect("billing:invoice_create")

    due_date_input = request.POST.get("due_date") or None
    due_date = None
    if due_date_input:
        try:
            due_date = datetime.fromisoformat(due_date_input).date()
        except Exception:
            messages.warning(request, "Could not parse due date; using payment term defaults.")

    currency_code = request.POST.get("currency") or getattr(
        organization, "base_currency_code_id", None
    )
    currency = Currency.objects.filter(currency_code=currency_code).first()
    if not currency:
        messages.error(request, "Please configure at least one currency before creating invoices.")
        return redirect("billing:invoice_create")

    payment_term = None
    payment_term_id = request.POST.get("payment_term")
    if payment_term_id:
        payment_term = PaymentTerm.objects.filter(
            payment_term_id=payment_term_id,
            organization=organization,
            is_active=True,
        ).first()
    if not payment_term:
        payment_term = getattr(customer, "payment_term", None)

    try:
        exchange_rate = Decimal(request.POST.get("exchange_rate") or "1")
    except Exception:
        exchange_rate = Decimal("1")

    warehouse = None
    warehouse_id = request.POST.get("warehouse")
    if warehouse_id:
        warehouse = Warehouse.objects.filter(
            warehouse_id=warehouse_id, organization=organization
        ).first()

    line_indices = [int(idx) for idx in request.POST.getlist("line_index[]") if idx]
    line_indices.sort()
    discount_percent = Decimal(request.POST.get("discount_percent") or "0")
    lines = []
    for idx in line_indices:
        description = (request.POST.get(f"description_{idx}", "") or "").strip()
        if not description:
            continue

        revenue_account_id = request.POST.get(f"revenue_account_{idx}")
        revenue_account = ChartOfAccount.objects.filter(
            account_id=revenue_account_id,
            organization=organization,
        ).first()

        quantity = Decimal(request.POST.get(f"quantity_{idx}", 0) or 0)
        unit_price = Decimal(request.POST.get(f"unit_price_{idx}", 0) or 0)
        line_subtotal = quantity * unit_price
        discount_amount = (
            (line_subtotal * discount_percent / Decimal("100")).quantize(Decimal("0.01"))
            if discount_percent
            else Decimal("0")
        )
        net_base = line_subtotal - discount_amount

        tax_code_ids = request.POST.getlist(f"tax_codes_{idx}") or []
        tax_amount, breakdown, tax_codes = _gather_tax_breakdown(
            net_base, tax_code_ids, organization, invoice_date
        )

        product_code = request.POST.get(f"product_code_{idx}", "") or ""
        product_id = request.POST.get(f"product_id_{idx}") or None

        if not revenue_account and product_id:
            product = Product.objects.filter(pk=product_id, organization=organization).first()
            if product and product.income_account:
                revenue_account = product.income_account

        if not revenue_account:
            messages.error(request, "Each line needs a revenue account.")
            return redirect("billing:invoice_create")

        lines.append(
            {
                "description": description,
                "product_code": product_code,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_amount": discount_amount,
                "revenue_account": revenue_account,
                "tax_code": tax_codes[0] if tax_codes else None,
                "tax_amount": tax_amount,
                "tax_breakdown": breakdown,
            }
        )

    if not lines:
        messages.error(request, "Add at least one invoice line.")
        return redirect("billing:invoice_create")

    service = SalesInvoiceService(request.user)
    metadata = {"discount_percent": str(discount_percent)}

    try:
        with transaction.atomic():
            invoice = service.create_invoice(
                organization=organization,
                customer=customer,
                invoice_number=None,
                invoice_date=invoice_date,
                currency=currency,
                lines=lines,
                payment_term=payment_term,
                due_date=due_date,
                exchange_rate=exchange_rate,
                metadata=metadata,
            )
            invoice.reference_number = request.POST.get("reference_number", "") or ""
            invoice.notes = request.POST.get("notes", "") or ""
            invoice.warehouse = warehouse
            invoice.save(update_fields=["reference_number", "notes", "warehouse"])

            if action == "post":
                service.validate_invoice(invoice)
                requested_journal_type = request.POST.get("journal_type")
                journal_type = (
                    JournalType.objects.filter(
                        journal_type_id=requested_journal_type,
                        organization=organization,
                    ).first()
                    if requested_journal_type
                    else JournalType.objects.filter(
                        organization=organization, code__icontains="sales"
                    )
                    .order_by("journal_type_id")
                    .first()
                ) or JournalType.objects.filter(
                    organization=organization
                ).order_by("journal_type_id").first()

                if not journal_type:
                    messages.error(
                        request, "No journal type is configured for posting sales invoices."
                    )
                    return redirect("billing:invoice_detail", invoice_id=invoice.invoice_id)

                service.post_invoice(invoice, journal_type, submit_to_ird=True, warehouse=warehouse)
                messages.success(
                    request,
                    "Invoice posted. IRD submission has been queued.",
                )
            else:
                messages.success(request, "Draft invoice saved.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Error creating invoice: {exc}")
        return redirect("billing:invoice_create")

    return redirect("billing:invoice_detail", invoice_id=invoice.invoice_id)


# ---------------------------------------------------------------------------
# Detail/listing
# ---------------------------------------------------------------------------
@login_required
def invoice_detail(request, invoice_id):
    """View invoice details"""
    organization = _get_active_org(request)
    invoice = (
        SalesInvoice.objects.select_related("customer", "currency", "journal")
        .prefetch_related("lines")
        .filter(invoice_id=invoice_id, organization=organization)
        .first()
    )
    if not invoice:
        return redirect("billing:invoice_list")

    lines = invoice.lines.select_related("tax_code", "revenue_account").all()
    line_taxes, tax_summary = _tax_lines_for_invoice(invoice)

    journal_types = JournalType.objects.filter(
        organization=organization,
        is_active=True,
    ).order_by("name")

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "invoice": invoice,
            "lines": lines,
            "journal_types": journal_types,
            "line_taxes": line_taxes,
            "tax_summary": tax_summary,
        },
    )


@login_required
def invoice_list(request):
    """List all invoices with filters"""
    organization = _get_active_org(request)
    invoices = (
        SalesInvoice.objects.filter(organization=organization)
        .select_related("customer", "currency")
        .order_by("-invoice_date")
    )

    status = request.GET.get("status")
    if status:
        invoices = invoices.filter(status=status)

    date_from = request.GET.get("date_from")
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
    date_to = request.GET.get("date_to")
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)

    customer_id = request.GET.get("customer")
    if customer_id:
        invoices = invoices.filter(customer_id=customer_id)

    currency_code = request.GET.get("currency")
    if currency_code:
        invoices = invoices.filter(currency__currency_code=currency_code)

    ird_status = request.GET.get("ird_status")
    if ird_status:
        invoices = invoices.filter(ird_status=ird_status)

    paginator = Paginator(invoices, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    customers = Customer.objects.filter(
        organization=organization,
        is_active=True,
    ).order_by("display_name")

    currencies = Currency.objects.filter(is_active=True).order_by("currency_code")

    return render(
        request,
        "billing/invoice_list.html",
        {
            "invoices": page_obj,
            "status_choices": SalesInvoice.STATUS_CHOICES,
            "ird_status_choices": [
                ("pending", "Pending"),
                ("synced", "Synced"),
                ("failed", "Failed"),
                ("cancelled", "Cancelled"),
            ],
            "customers": customers,
            "currencies": currencies,
            "current_status": status or "",
            "current_customer": customer_id or "",
            "current_currency": currency_code or "",
            "current_ird_status": ird_status or "",
            "current_date_from": date_from or "",
            "current_date_to": date_to or "",
        },
    )


# ---------------------------------------------------------------------------
# Print/IRD actions
# ---------------------------------------------------------------------------
@login_required
def invoice_pdf(request, invoice_id):
    """Generate PDF with QR code for IRD-synced invoices"""
    organization = _get_active_org(request)
    invoice = (
        SalesInvoice.objects.select_related("customer", "currency")
        .prefetch_related("lines")
        .filter(invoice_id=invoice_id, organization=organization)
        .first()
    )
    if not invoice:
        return redirect("billing:invoice_list")

    qr_base64 = None
    if invoice.ird_status == "synced" and getattr(invoice, "ird_qr_data", None):
        try:
            import base64
            from io import BytesIO

            import qrcode

            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(invoice.ird_qr_data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        except Exception:
            logger.warning("qr.generation_failed", exc_info=True)

    line_taxes, tax_summary = _tax_lines_for_invoice(invoice)
    template_style = _resolve_template_style(request, organization)
    template_name = f"billing/prints/invoice_{template_style}.html"

    html_string = render_to_string(
        template_name,
        {
            "invoice": invoice,
            "lines": invoice.lines.all(),
            "qr_base64": qr_base64,
            "branding": get_branding_from_request(request),
            "line_taxes": line_taxes,
            "tax_summary": tax_summary,
            "template_style": template_style,
        },
    )

    html = HTML(string=html_string, base_url=request.build_absolute_uri("/"))
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Invoice-{invoice.invoice_number}.pdf"'

    try:
        record_invoice_print(invoice)
    except Exception:
        logger.warning("ird.print_log_failed", exc_info=True)

    return response


@login_required
@require_POST
def submit_to_ird(request, invoice_id):
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=_get_active_org(request),
    )

    if invoice.ird_status == "synced":
        messages.warning(request, "Invoice already submitted to IRD")
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    if invoice.status != "posted":
        messages.error(request, "Only posted invoices can be sent to IRD.")
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    service = IRDSubmissionService(request.user)
    task = service.enqueue_invoice(invoice)
    if invoice.ird_status != "pending":
        invoice.ird_status = "pending"
        invoice.save(update_fields=["ird_status", "updated_at"])
    messages.success(
        request,
        f"Invoice queued for IRD submission (task #{task.submission_id}).",
    )

    return redirect("billing:invoice_detail", invoice_id=invoice_id)


@login_required
@require_POST
def post_invoice(request, invoice_id):
    """Post a draft or validated invoice"""
    organization = _get_active_org(request)
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=organization,
    )

    if invoice.status not in ["draft", "validated"]:
        messages.error(request, "Only draft or validated invoices can be posted.")
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    journal_type_id = request.POST.get("journal_type")
    if journal_type_id:
        journal_type = JournalType.objects.filter(
            journal_type_id=journal_type_id,
            organization=organization,
            is_active=True,
        ).first()
    else:
        journal_type = JournalType.objects.filter(
            organization=organization,
            code__icontains="sales",
            is_active=True,
        ).first()

    if not journal_type:
        journal_type = JournalType.objects.filter(
            organization=organization,
            is_active=True,
        ).first()

    if not journal_type:
        messages.error(request, "No journal type configured for posting.")
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    warehouse = invoice.warehouse or Warehouse.objects.filter(
        organization=organization,
        is_active=True,
    ).first()

    submit_to_ird = request.POST.get("submit_to_ird") == "true"

    try:
        service = SalesInvoiceService(request.user)

        if invoice.status == "draft":
            service.validate_invoice(invoice)

        journal = service.post_invoice(
            invoice,
            journal_type,
            submit_to_ird=submit_to_ird,
            warehouse=warehouse,
        )

        messages.success(
            request,
            f"Invoice #{invoice.invoice_number} posted successfully. Journal #{journal.journal_number} created.",
        )

        if submit_to_ird and invoice.ird_status == "pending":
            messages.info(request, "Invoice has been queued for IRD submission.")

    except ValidationError as exc:
        messages.error(request, f"Validation error: {exc}")
    except Exception as exc:
        messages.error(request, f"Error posting invoice: {exc}")

    return redirect("billing:invoice_detail", invoice_id=invoice_id)


@login_required
def send_to_ird(request, invoice_id):
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=_get_active_org(request),
    )

    if invoice.ird_status == "synced":
        messages.warning(request, "Invoice already submitted to IRD")
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    if invoice.status != "posted":
        messages.error(request, "Only posted invoices can be sent to IRD.")
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    service = IRDSubmissionService(request.user)
    task = service.enqueue_invoice(invoice)
    if invoice.ird_status != "pending":
        invoice.ird_status = "pending"
        invoice.save(update_fields=["ird_status", "updated_at"])
    messages.success(
        request,
        f"Invoice queued for IRD submission (task #{task.submission_id}).",
    )

    return redirect("billing:invoice_detail", invoice_id=invoice_id)


@login_required
def cancel_invoice(request, invoice_id):
    if request.method != "POST":
        return redirect("billing:invoice_detail", invoice_id=invoice_id)

    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=_get_active_org(request),
    )

    reason = request.POST.get("reason", "")

    if invoice.ird_status == "synced":
        invoice.ird_status = "cancelled"
        messages.warning(
            request,
            "Marked IRD status as cancelled. Please ensure the cancellation is reflected on the IRD portal if required.",
        )

    invoice.status = "cancelled"
    if reason:
        invoice.notes = f"{invoice.notes}\nCancelled: {reason}".strip()
    invoice.save(update_fields=["status", "notes", "ird_status", "updated_at"])

    messages.success(request, "Invoice cancelled.")
    return redirect("billing:invoice_detail", invoice_id=invoice_id)


@login_required
def export_tally(request):
    organization = _get_active_org(request)
    if request.method == "GET":
        return render(request, "billing/export_tally.html")

    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")

    invoices = SalesInvoice.objects.filter(
        organization=organization,
        status="posted",
        invoice_date__range=[start_date, end_date],
    )

    from accounting.services.tally_export import TallyXMLExporter

    exporter = TallyXMLExporter(organization.name)
    xml_data = exporter.export_sales_invoices(invoices, start_date, end_date)

    response = HttpResponse(xml_data, content_type="application/xml")
    response["Content-Disposition"] = (
        f'attachment; filename="tally_export_{start_date}_{end_date}.xml"'
    )
    return response


# URL Configuration (add to billing/urls.py)
"""
from django.urls import path
from billing import views

urlpatterns = [
    path('invoice/create/', views.invoice_create, name='invoice_create'),
    path('invoice/<uuid:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/save/', views.invoice_save, name='invoice_save'),
    
    # HTMX endpoints
    path('htmx/customer-search/', views.customer_search, name='customer_search'),
    path('htmx/product-search/', views.product_search, name='product_search'),
    path('htmx/add-line/', views.add_invoice_line, name='add_invoice_line'),
    path('htmx/calculate-line/', views.calculate_line_total, name='calculate_line_total'),
    path('htmx/calculate-total/', views.calculate_invoice_total, name='calculate_invoice_total'),
]
"""
