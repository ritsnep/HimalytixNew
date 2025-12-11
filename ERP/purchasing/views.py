from __future__ import annotations

from typing import Optional

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum, Count
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

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
        .select_related("supplier", "currency")
        .order_by("-invoice_date", "-id")
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
    search = request.GET.get("q", "").strip()
    invoices = (
        PurchaseInvoice.objects.filter(organization=organization)
        .select_related("supplier", "currency")
        .order_by("-invoice_date", "-id")
    )
    if search:
        invoices = invoices.filter(
            Q(number__icontains=search)
            | Q(supplier__display_name__icontains=search)
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
        PurchaseInvoice.objects.select_related("supplier", "currency"),
        pk=pk,
        organization=organization,
    )
    if getattr(request, "htmx", False):
        return _render_invoice_detail(request, invoice)

    context = {
        "page_title": f"Purchase Invoice {invoice.number}",
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
                invoice.status = PurchaseInvoice.Status.DRAFT
                invoice.save(skip_recalc=True)
                formset.instance = invoice
                formset.save()
                invoice.recalc_totals()
                invoice.save(skip_recalc=True)
            return redirect("purchasing:invoice-table")
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
    return render(request, "purchasing/invoice_form_page.html", context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "post"))
@require_POST
def invoice_post(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    try:
        post_purchase_invoice(invoice)
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
        alert="Invoice posted successfully.",
    )
    response["HX-Trigger"] = "purchaseInvoiceChanged"
    return response


@login_required
@permission_required(("purchasing", "purchaseinvoice", "delete"))
@require_POST
def invoice_delete(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(PurchaseInvoice, pk=pk, organization=organization)
    if invoice.status != PurchaseInvoice.Status.DRAFT:
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
        return _render_invoice_detail(
            request,
            invoice,
            alert=str(exc),
            alert_level="danger",
        )
    response = _render_invoice_detail(
        request,
        invoice,
        alert="Invoice reversed and moved to draft.",
    )
    response["HX-Trigger"] = "purchaseInvoiceChanged"
    return response


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
        return _render_invoice_detail(
            request,
            invoice,
            alert=str(exc),
            alert_level="danger",
        )
    response = _render_invoice_detail(
        request,
        invoice,
        alert="Invoice returned and reversal posted.",
    )
    response["HX-Trigger"] = "purchaseInvoiceChanged"
    return response


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
            "draft": inv_qs.filter(status=PurchaseInvoice.Status.DRAFT).count(),
            "posted": inv_qs.filter(status=PurchaseInvoice.Status.POSTED).count(),
            "sum_total": inv_qs.aggregate(total=Sum("total_amount"))["total"] or 0,
            "sum_posted": inv_qs.filter(status=PurchaseInvoice.Status.POSTED).aggregate(total=Sum("total_amount"))["total"] or 0,
        },
        "po_sum_total": po_qs.aggregate(total=Sum("total_amount"))["total"] or 0,
        "gr_posted_count": gr_qs.filter(status=GoodsReceipt.Status.POSTED).count(),
        "landed_backlog": lc_qs.filter(is_applied=False).select_related("purchase_invoice")[:25],
        "landed_pending_total": lc_qs.filter(is_applied=False).aggregate(total=Sum("cost_lines__amount"))["total"] or 0,
        "landed_applied_total": lc_qs.filter(is_applied=True).aggregate(total=Sum("cost_lines__amount"))["total"] or 0,
        "recent_pos": po_qs.select_related("vendor").order_by("-created_at")[:10],
        "recent_grs": gr_qs.select_related("purchase_order").order_by("-receipt_date")[:10],
        "recent_invoices": inv_qs.select_related("supplier").order_by("-invoice_date")[:10],
    }

    return render(request, "purchasing/reports.html", context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def landed_cost_list_page(request):
    organization = _organization(request)
    docs = (
        LandedCostDocument.objects.filter(organization=organization)
        .select_related("purchase_invoice__supplier")
        .prefetch_related("cost_lines")
        .annotate(
            cost_total=Sum("cost_lines__amount"),
            cost_count=Count("cost_lines"),
        )
        .order_by("-document_date", "-id")
    )
    context = {
        "page_title": "Landed Cost Documents",
        "page_subtitle": "Allocate freight, duty, and other costs across receipts.",
        "documents": docs[:300],
    }
    return render(request, "purchasing/landed_cost_list_page.html", context)
