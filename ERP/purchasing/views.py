from __future__ import annotations

from typing import Optional

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation

from usermanagement.utils import PermissionUtils, permission_required

from purchasing.forms import (
    LandedCostDocumentForm,
    LandedCostLineFormSet,
    PurchaseInvoiceForm,
    PurchaseInvoiceLineFormSet,
)
from purchasing.models import (
    LandedCostDocument,
    PurchaseInvoice,
    PurchaseOrder,
    GoodsReceipt,
)
from purchasing.services import (
    ProcurementPostingError,
    apply_landed_cost_document,
    post_purchase_invoice,
    reverse_purchase_invoice,
)


def _organization(request):
    organization = getattr(request, "organization", None)
    if not organization and getattr(request, "user", None):
        organization = request.user.get_active_organization()

    if not organization:
        raise PermissionDenied("Active organization is required for purchasing workspace.")

    # keep request/user caches in sync for the rest of the request lifecycle
    setattr(request, "organization", organization)
    if hasattr(request.user, "set_active_organization"):
        request.user.set_active_organization(organization)
    return organization


def _render_invoice_detail(
    request,
    invoice: PurchaseInvoice,
    *,
    alert: Optional[str] = None,
    alert_level: str = "success",
):
    invoice.refresh_from_db()
    context = {
        "invoice": invoice,
        "landed_doc": getattr(invoice, "landed_cost_document", None),
        "alert_message": alert,
        "alert_level": alert_level,
    }
    return render(request, "purchasing/partials/invoice_detail.html", context)


def _render_invoice_form(request, context, *, status=200):
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/invoice_form.html", context, status=status)
    return render(request, "purchasing/invoice_form_page.html", context, status=status)


def _safe_decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _calc_invoice_totals_from_post(request) -> dict:
    total_qty = Decimal("0")
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    total_forms = int(request.POST.get("lines-TOTAL_FORMS", 0) or 0)
    for idx in range(total_forms):
        if request.POST.get(f"lines-{idx}-DELETE") in ("on", "true", "1"):
            continue
        qty = _safe_decimal(request.POST.get(f"lines-{idx}-quantity"))
        unit_cost = _safe_decimal(request.POST.get(f"lines-{idx}-unit_price"))
        vat_rate = _safe_decimal(request.POST.get(f"lines-{idx}-vat_rate"))
        line_total = qty * unit_cost
        total_qty += qty
        subtotal += line_total
        tax_total += (line_total * vat_rate / Decimal("100"))
    grand_total = subtotal + tax_total
    return {
        "total_qty": f"{total_qty:.2f}",
        "subtotal": f"{subtotal:.2f}",
        "tax_total": f"{tax_total:.2f}",
        "grand_total": f"{grand_total:.2f}",
    }


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def workspace(request):
    _organization(request)
    return render(request, "purchasing/workspace.html")


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def invoice_list(request):
    organization = _organization(request)
    search = request.GET.get("q", "").strip()
    invoices = (
        PurchaseInvoice.objects.filter(organization=organization)
        .select_related("vendor", "currency")
        .order_by("-invoice_date", "-invoice_id")
    )
    if search:
        invoices = invoices.filter(
            Q(number__icontains=search)
            | Q(supplier__display_name__icontains=search)
        )
    context = {
        "invoices": invoices[:100],
        "query": search,
    }
    return render(request, "purchasing/partials/invoice_list.html", context)



@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def invoice_list_page(request):
    organization = _organization(request)
    if request.method == "POST":
        # Example: handle bulk actions or advanced filtering
        action = request.POST.get("action")
        selected_ids = request.POST.getlist("selected_invoices")
        if action and selected_ids:
            updated = 0
            for pk in selected_ids:
                try:
                    invoice = PurchaseInvoice.objects.get(pk=pk, organization=organization)
                    if action == "delete" and invoice.status == 'draft':
                        invoice.delete()
                        updated += 1
                    elif action == "post":
                        try:
                            post_purchase_invoice(invoice)
                            updated += 1
                        except ProcurementPostingError as exc:
                            messages.error(request, f"Invoice {invoice.invoice_number}: {exc}")
                except PurchaseInvoice.DoesNotExist:
                    messages.error(request, f"Invoice with ID {pk} not found.")
            if updated:
                messages.success(request, f"{updated} invoice(s) processed.")
            return redirect("purchasing:invoice-table")
        else:
            messages.error(request, "No action or invoices selected.")
            return redirect("purchasing:invoice-table")
    search = request.GET.get("q", "").strip()
    invoices = (
        PurchaseInvoice.objects.filter(organization=organization)
        .select_related("vendor", "currency")
        .order_by("-invoice_date", "-invoice_id")
    )
    if search:
        invoices = invoices.filter(
            Q(number__icontains=search)
            | Q(vendor_display_name__icontains=search)
        )
    context = {
        "page_title": "Purchase Invoices",
        "page_subtitle": "All supplier invoices with totals and status.",
        "invoices": invoices[:500],
        "query": search,
        "create_url": reverse("purchasing:invoice-create"),
        "create_button_text": "New Invoice",
    }
    return render(request, "purchasing/invoice_list_page.html", context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def invoice_detail(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(
        PurchaseInvoice.objects.select_related("vendor", "currency"),
        pk=pk,
        organization=organization,
    )
    if getattr(request, "htmx", False):
        return _render_invoice_detail(request, invoice)

    context = {
        "page_title": f"Purchase Invoice {invoice.invoice_number}",
        "invoice": invoice,
        "landed_doc": getattr(invoice, "landed_cost_document", None),
    }
    return render(request, "purchasing/invoice_detail_page.html", context)


@login_required
def invoice_form(request, pk: Optional[int] = None):
    organization = _organization(request)
    invoice = None
    if pk:
        invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
        required_action = "change"
    else:
        required_action = "add"
    if not PermissionUtils.has_permission(
        request.user, organization, "purchasing", "purchaseinvoice", required_action
    ):
        raise PermissionDenied("You do not have permission to edit or create purchase invoices.")
    form = PurchaseInvoiceForm(
        request.POST or None,
        instance=invoice,
        organization=organization,
    )
    formset = PurchaseInvoiceLineFormSet(
        request.POST or None,
        instance=invoice,
        prefix="lines",
        organization=organization,
    )
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.organization = organization
                invoice.status = 'draft'
                invoice.save(skip_recalc=True)
                formset.instance = invoice
                formset.save()
                invoice.recalc_totals()
                invoice.save(skip_recalc=True)
            if getattr(request, "htmx", False):
                response = _render_invoice_detail(
                    request,
                    invoice,
                    alert="Invoice saved successfully.",
                )
                response["HX-Trigger"] = "purchaseInvoiceChanged"
                return response
            messages.success(request, "Invoice saved successfully.")
            return redirect("purchasing:invoice-table")
        if getattr(request, "htmx", False):
            context = {
                "form": form,
                "line_formset": formset,
                "form_action": request.path,
                "is_edit": bool(pk),
                "page_title": "Purchase Invoice" if pk else "New Purchase Invoice",
                "form_title": "Purchase Invoice",
                "breadcrumbs": [("Purchasing", reverse("purchasing:invoice-table")), ("Invoice", None)],
                "alert_message": "Please correct the errors below.",
                "alert_level": "danger",
            }
            return _render_invoice_form(request, context, status=422)
    form_action = (
        reverse("purchasing:invoice-edit", kwargs={"pk": pk})
        if pk
        else reverse("purchasing:invoice-create")
    )
    context = {
        "form": form,
        "line_formset": formset,
        "form_action": form_action,
        "is_edit": bool(pk),
        "page_title": "Purchase Invoice" if pk else "New Purchase Invoice",
        "form_title": "Purchase Invoice",
        "breadcrumbs": [("Purchasing", reverse("purchasing:invoice-table")), ("Invoice", None)],
    }
    return _render_invoice_form(request, context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "post"))
@require_POST
def invoice_post(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    try:
        post_purchase_invoice(invoice)
    except ProcurementPostingError as exc:
        if getattr(request, "htmx", False):
            return _render_invoice_detail(
                request,
                invoice,
                alert=str(exc),
                alert_level="danger",
            )
        messages.error(request, str(exc))
        return redirect("purchasing:invoice-detail", pk=pk)
    if getattr(request, "htmx", False):
        response = _render_invoice_detail(
            request,
            invoice,
            alert="Invoice posted successfully.",
        )
        response["HX-Trigger"] = "purchaseInvoiceChanged"
        return response
    messages.success(request, "Invoice posted successfully.")
    return redirect("purchasing:invoice-table")


@login_required
@permission_required(("purchasing", "purchaseinvoice", "delete"))
@require_POST
def invoice_delete(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    if invoice.status != 'draft':
        return _render_invoice_detail(
            request,
            invoice,
            alert="Posted invoices cannot be deleted.",
            alert_level="warning",
        )

    invoice.delete()

    if getattr(request, "htmx", False):
        response = render(
            request,
            "purchasing/partials/invoice_deleted.html",
            {"alert_message": "Purchase invoice deleted."},
        )
        response["HX-Trigger"] = "purchaseInvoiceChanged"
        return response

    messages.success(request, "Purchase invoice deleted.")
    return redirect("purchasing:invoice-table")


@login_required
@permission_required(("purchasing", "purchaseinvoice", "change"))
@require_POST
def invoice_reverse(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    try:
        reverse_purchase_invoice(invoice, user=request.user)
    except ProcurementPostingError as exc:
        if getattr(request, "htmx", False):
            return _render_invoice_detail(
                request,
                invoice,
                alert=str(exc),
                alert_level="danger",
            )
        messages.error(request, str(exc))
        return redirect("purchasing:invoice-detail", pk=pk)
    if getattr(request, "htmx", False):
        response = _render_invoice_detail(
            request,
            invoice,
            alert="Invoice reversed and moved to draft.",
        )
        response["HX-Trigger"] = "purchaseInvoiceChanged"
        return response
    messages.success(request, "Invoice reversed and moved to draft.")
    return redirect("purchasing:invoice-table")


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
@require_POST
def invoice_recalc(request):
    totals = _calc_invoice_totals_from_post(request)
    return render(request, "purchasing/partials/invoice_totals.html", totals)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "change"))
@require_POST
def invoice_validate(request, pk: Optional[int] = None):
    organization = _organization(request)
    invoice = None
    if pk:
        invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    form = PurchaseInvoiceForm(
        request.POST or None,
        instance=invoice,
        organization=organization,
    )
    formset = PurchaseInvoiceLineFormSet(
        request.POST or None,
        instance=invoice,
        prefix="lines",
        organization=organization,
    )
    context = {
        "form": form,
        "line_formset": formset,
        "form_action": request.path,
        "is_edit": bool(pk),
        "page_title": "Purchase Invoice" if pk else "New Purchase Invoice",
        "form_title": "Purchase Invoice",
        "breadcrumbs": [("Purchasing", reverse("purchasing:invoice-table")), ("Invoice", None)],
    }
    if form.is_valid() and formset.is_valid():
        context["alert_message"] = "Validation passed."
        context["alert_level"] = "success"
        return _render_invoice_form(request, context, status=200)
    context["alert_message"] = "Please correct the errors below."
    context["alert_level"] = "danger"
    return _render_invoice_form(request, context, status=422)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "change"))
@require_POST
def invoice_return(request, pk: int):
    """Alias for reverse with user-facing wording."""
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    try:
        reverse_purchase_invoice(invoice, user=request.user)
    except ProcurementPostingError as exc:
        if getattr(request, "htmx", False):
            return _render_invoice_detail(
                request,
                invoice,
                alert=str(exc),
                alert_level="danger",
            )
        messages.error(request, str(exc))
        return redirect("purchasing:invoice-detail", pk=pk)
    if getattr(request, "htmx", False):
        response = _render_invoice_detail(
            request,
            invoice,
            alert="Invoice returned and reversal posted.",
        )
        response["HX-Trigger"] = "purchaseInvoiceChanged"
        return response
    messages.success(request, "Invoice returned and reversal posted.")
    return redirect("purchasing:invoice-table")


@login_required
@permission_required(("purchasing", "purchaseinvoice", "change"))
def landed_cost_form(request, invoice_id: int, doc_id: Optional[int] = None):
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=invoice_id, organization=organization)
    document = None
    if doc_id:
        document = get_object_or_404(
            LandedCostDocument,
            pk=doc_id,
            purchase_invoice=invoice,
            organization=organization,
        )
    form = LandedCostDocumentForm(request.POST or None, instance=document)
    formset = LandedCostLineFormSet(
        request.POST or None,
        instance=document,
        prefix="costs",
        organization=organization,
    )
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                document = form.save(commit=False)
                document.organization = organization
                document.purchase_invoice = invoice
                document.save()
                formset.instance = document
                formset.save()
            return redirect("purchasing:landed-cost-table")
    if doc_id:
        form_action = reverse(
            "purchasing:landed-cost-edit",
            kwargs={"invoice_id": invoice_id, "doc_id": doc_id},
        )
    else:
        form_action = reverse(
            "purchasing:landed-cost-create", kwargs={"invoice_id": invoice_id}
        )
    context = {
        "invoice": invoice,
        "form": form,
        "line_formset": formset,
        "form_action": form_action,
        "page_title": "Landed Cost",
        "form_title": "Landed Cost",
        "breadcrumbs": [("Purchasing", reverse("purchasing:landed-cost-table")), ("Landed Cost", None)],
    }
    return render(request, "purchasing/landed_cost_form_page.html", context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "post"))
@require_POST
def landed_cost_apply(request, doc_id: int):
    organization = _organization(request)
    document = get_object_or_404(
        LandedCostDocument.objects.select_related("purchase_invoice"),
        pk=doc_id,
        organization=organization,
    )
    invoice = document.purchase_invoice
    try:
        apply_landed_cost_document(document)
    except ProcurementPostingError as exc:
        return _render_invoice_detail(
            request,
            invoice,
            alert=str(exc),
            alert_level="danger",
        )
    response = _render_invoice_detail(
        request,
        invoice,
        alert="Landed cost applied to inventory.",
    )
    response["HX-Trigger"] = "landedCostChanged"
    return response


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def reports(request):
    organization = _organization(request)

    po_qs = PurchaseOrder.objects.filter(organization=organization)
    gr_qs = GoodsReceipt.objects.filter(organization=organization)
    inv_qs = PurchaseInvoice.objects.filter(organization=organization)
    lc_qs = LandedCostDocument.objects.filter(organization=organization)

    context = {
        "page_title": "Purchasing Reports",
        "po_counts": {
            "draft": po_qs.filter(status=PurchaseOrder.Status.DRAFT).count(),
            "approved": po_qs.filter(status=PurchaseOrder.Status.APPROVED).count(),
            "sent": po_qs.filter(status=PurchaseOrder.Status.SENT).count(),
            "received": po_qs.filter(status=PurchaseOrder.Status.RECEIVED).count(),
        },
        "gr_counts": {
            "draft": gr_qs.filter(status=GoodsReceipt.Status.DRAFT).count(),
            "posted": gr_qs.filter(status=GoodsReceipt.Status.POSTED).count(),
        },
        "invoice_totals": {
            "draft": inv_qs.filter(status='draft').count(),
            "posted": inv_qs.filter(status='posted').count(),
            "sum_total": inv_qs.aggregate(total=Sum("total"))["total"] or 0,
            "sum_posted": inv_qs.filter(status='posted').aggregate(total=Sum("total"))["total"] or 0,
        },
        "po_sum_total": po_qs.aggregate(total=Sum("total_amount"))["total"] or 0,
        "gr_posted_count": gr_qs.filter(status=GoodsReceipt.Status.POSTED).count(),
        "landed_backlog": lc_qs.filter(is_applied=False).select_related("purchase_invoice")[:25],
        "landed_pending_total": lc_qs.filter(is_applied=False).aggregate(total=Sum("cost_lines__amount"))["total"] or 0,
        "landed_applied_total": lc_qs.filter(is_applied=True).aggregate(total=Sum("cost_lines__amount"))["total"] or 0,
        "recent_pos": po_qs.select_related("vendor").order_by("-created_at")[:10],
        "recent_grs": gr_qs.select_related("purchase_order").order_by("-receipt_date")[:10],
        "recent_invoices": inv_qs.select_related("vendor").order_by("-invoice_date")[:10],
    }

    return render(request, "purchasing/reports.html", context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def landed_cost_list_page(request):
    organization = _organization(request)
    docs = (
        LandedCostDocument.objects.filter(organization=organization)
        .select_related("purchase_invoice__vendor")
        .prefetch_related("cost_lines")
        .annotate(
            cost_total=Sum("cost_lines__amount"),
            cost_count=Count("cost_lines"),
        )
        .order_by("-document_date", "-landed_cost_id")
    )
    context = {
        "page_title": "Landed Cost Documents",
        "page_subtitle": "Allocate freight, duty, and other costs across receipts.",
        "documents": docs[:300],
    }
    return render(request, "purchasing/landed_cost_list_page.html", context)


# ===== LEGACY WRAPPER FUNCTIONS (for backward compatibility) =====
# These delegate to the legacy class-based views but can be referenced by path()

@login_required
@permission_required("purchasing.view_purchaseorder")
def po_list_page_legacy(request):
    """
    Legacy wrapper for PO list page.
    Imports and delegates to POListPageView from views_po.
    """
    from purchasing.views_po import POListPageView
    view = POListPageView.as_view()
    return view(request)


@login_required
@permission_required("purchasing.view_goodsreceipt")
def gr_list_page_legacy(request):
    """
    Legacy wrapper for GR list page.
    Imports and delegates to GRListPageView from views_gr.
    """
    from purchasing.views_gr import GRListPageView
    view = GRListPageView.as_view()
    return view(request)
