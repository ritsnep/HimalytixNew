"""
Views for the HTMX-driven Sales Invoice module.

This module exposes a set of endpoints to render the new Sales Invoice
interface, handle incremental updates via HTMX requests and finalise
drafts into real SalesInvoice records. Each HTMX action (recalc,
add-line, delete-line, apply-order, date conversions) posts back
changes which are applied on the server and returns only the parts of
the page that need updating via `hx-swap-oob`. Non-HTMX submissions
save the draft into a full `SalesInvoice` using the existing
SalesInvoiceService.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import SalesInvoiceDraft
from .services import SalesInvoiceDraftService


def new(request: HttpRequest, draft_id: str | None = None) -> HttpResponse:
    """Render a new or existing Sales Invoice draft."""
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    # Ensure there is at least one line for the initial render
    if draft.lines.count() == 0:
        SalesInvoiceDraftService.add_line(draft)
    # Optionally allocate invoice number
    SalesInvoiceDraftService.get_next_invoice_number(draft)
    # Load lookup data
    lookups = SalesInvoiceDraftService.get_lookup_data()
    # UI column prefs may be stored in session or DB; for simplicity read from draft snapshot or defaults
    ui_cols = {
        "hs_code": True,
        "description": True,
        "discount": True,
        "net_rate": True,
    }
    # Compose context
    context = {
        "draft": draft,
        **lookups,
        "payment_modes": lookups["payment_modes"],
        "ui_cols": ui_cols,
        "buyer_snapshot": draft.buyer_snapshot,
    }
    return render(request, "vouchers/sales_invoice/new.html", context)


@require_POST
def recalc(request: HttpRequest, draft_id: str) -> HttpResponse:
    """Handle a recalc request when any field changes."""
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.recalc(draft)
    # Return partial update
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def add_line(request: HttpRequest, draft_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.add_line(draft)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def delete_line(request: HttpRequest, draft_id: str, line_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.delete_line(draft, line_id)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def add_receipt(request: HttpRequest, draft_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.add_receipt(draft)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def delete_receipt(request: HttpRequest, draft_id: str, receipt_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.delete_receipt(draft, receipt_id)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


def buyer_info(request: HttpRequest, draft_id: str) -> HttpResponse:
    """Fetch and display buyer info panel based on buyer_id."""
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    # Optionally update buyer_id from request
    buyer_id = request.GET.get("buyer_id") or request.POST.get("buyer_id")
    if buyer_id:
        draft.buyer_id = int(buyer_id)
        # Here you could query customer info and assign snapshot; for now stub
        draft.buyer_snapshot = {
            "balance": "12500.00",
            "pan": "123456789",
            "credit_limit": "500000.00",
            "overdue": "2500.00",
        }
        draft.save(update_fields=["buyer_id", "buyer_snapshot"])
    context = {"buyer_snapshot": draft.buyer_snapshot}
    return render(request, "vouchers/sales_invoice/partials/_buyer_info.html", context)


@require_POST
def date_bs_to_ad(request: HttpRequest, draft_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.convert_bs_to_ad(draft)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def date_ad_to_bs(request: HttpRequest, draft_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.convert_ad_to_bs(draft)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def columns_pref(request: HttpRequest, draft_id: str) -> HttpResponse:
    """Persist column visibility preferences on the server.

    The client posts checkboxes named col_<key> and we update a JSON
    field or session. For simplicity we store prefs in the draft's
    buyer_snapshot. A separate model could be used instead.
    """
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    prefs = {
        "hs_code": request.POST.get("col_hs_code") is not None,
        "description": request.POST.get("col_description") is not None,
        "discount": request.POST.get("col_discount") is not None,
        "net_rate": request.POST.get("col_net_rate") is not None,
    }
    # Persist within buyer_snapshot for lack of dedicated model
    snapshot = draft.buyer_snapshot or {}
    snapshot["ui_cols"] = prefs
    draft.buyer_snapshot = snapshot
    draft.save(update_fields=["buyer_snapshot"])
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def apply_order(request: HttpRequest, draft_id: str) -> HttpResponse:
    """Populate lines from a selected order reference.

    This stub currently does not import lines; it simply recalculates
    totals. Extend this to fetch pending items from your sales order
    model and merge or replace existing draft lines accordingly.
    """
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    # TODO: merge or replace lines from order
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def refetch_no(request: HttpRequest, draft_id: str) -> HttpResponse:
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.get_next_invoice_number(draft)
    SalesInvoiceDraftService.recalc(draft)
    return render(request, "vouchers/sales_invoice/partials/_recalc_response.html", {"draft": draft, **SalesInvoiceDraftService.get_lookup_data()})


@require_POST
def save(request: HttpRequest, draft_id: str) -> HttpResponse:
    """Finalize the draft into a real Sales Invoice.

    This stub simply redirects back to the draft view. In a real
    implementation it would call the existing `SalesInvoiceService` to
    persist the draft into `SalesInvoice` and `SalesInvoiceLine`
    models, allocate journal entries and optionally post the invoice.
    """
    draft = SalesInvoiceDraftService.load_or_create(request.user if request.user.is_authenticated else None, draft_id)
    SalesInvoiceDraftService.update_from_post(draft, request.POST)
    SalesInvoiceDraftService.recalc(draft)
    # TODO: convert draft to real invoice using SalesInvoiceService
    # For now just redirect to the list or same page
    return redirect(reverse("vouchers_sales_invoice:new", kwargs={"draft_id": str(draft.id)}))


def cancel(request: HttpRequest, draft_id: str) -> HttpResponse:
    """Delete the draft and return to invoice list."""
    try:
        draft = SalesInvoiceDraft.objects.get(pk=draft_id)
        draft.delete()
    except SalesInvoiceDraft.DoesNotExist:
        pass
    # TODO: redirect to invoice list once integrated
    return redirect(reverse("vouchers_sales_invoice:new"))
