"""
Unified purchasing workflow views for Purchase Order, Goods Receipt, and Purchase Return.

Provides integrated forms with inline editing for:
- Purchase Orders (PO) with editable product/qty
- Goods Receipts (GR) with QC tracking
- Purchase Returns (PR) with reason tracking
- Landed Cost allocation and distribution
"""

from __future__ import annotations

from typing import Optional
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages

from usermanagement.utils import PermissionUtils, permission_required

from purchasing.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
    LandedCostDocument,
)
from purchasing.forms import (
    PurchaseOrderForm,
    PurchaseOrderLineFormSet,
    GoodsReceiptForm,
    GoodsReceiptLineFormSet,
    LandedCostDocumentForm,
    LandedCostLineFormSet,
)
from purchasing.services import (
    ProcurementPostingError,
    post_purchase_order,
    post_goods_receipt,
    apply_landed_cost_document,
)


def _organization(request):
    """Get active organization from request or raise error."""
    organization = getattr(request, "organization", None)
    if not organization and getattr(request, "user", None):
        organization = request.user.get_active_organization()

    if not organization:
        raise PermissionDenied("Active organization is required for purchasing workflow.")

    setattr(request, "organization", organization)
    if hasattr(request.user, "set_active_organization"):
        request.user.set_active_organization(organization)
    return organization


# ============================================================================
# PURCHASE ORDER UNIFIED FLOW
# ============================================================================

@login_required
@permission_required(("purchasing", "purchaseorder", "view"))
def po_unified_form(request, pk: Optional[int] = None):
    """
    Unified Purchase Order form with inline editable lines.
    Allows full CRUD of products, quantities, and pricing.
    """
    organization = _organization(request)
    po = None
    
    if pk:
        po = get_object_or_404(PurchaseOrder, pk=pk, organization=organization)
        required_action = "change"
    else:
        required_action = "add"
    
    if not PermissionUtils.has_permission(
        request.user, organization, "purchasing", "purchaseorder", required_action
    ):
        raise PermissionDenied("You do not have permission to edit or create purchase orders.")
    
    form = PurchaseOrderForm(
        request.POST or None,
        instance=po,
        organization=organization,
    )
    formset = PurchaseOrderLineFormSet(
        request.POST or None,
        instance=po,
        prefix="lines",
        organization=organization,
    )
    
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                po = form.save(commit=False)
                po.organization = organization
                po.status = PurchaseOrder.Status.DRAFT
                po.save(skip_recalc=True)
                formset.instance = po
                formset.save()
                po.recalc_totals()
                po.save(skip_recalc=True)
            
            messages.success(
                request,
                f"Purchase Order {po.number} saved successfully."
            )
            return redirect("purchasing:po_detail", pk=po.id)
    
    form_action = (
        reverse("purchasing:po_edit", kwargs={"pk": pk})
        if pk
        else reverse("purchasing:po_unified_create")
    )
    
    context = {
        "form": form,
        "line_formset": formset,
        "form_action": form_action,
        "is_edit": bool(pk),
        "page_title": "Edit Purchase Order" if pk else "New Purchase Order",
        "form_title": "Purchase Order",
        "breadcrumbs": [
            ("Purchasing", reverse("purchasing:po_table")),
            ("Purchase Order", None)
        ],
        "document_type": "purchase_order",
    }
    return render(request, "purchasing/unified_form.html", context)


@login_required
@permission_required(("purchasing", "purchaseorder", "change"))
@require_POST
def po_approve(request, pk: int):
    """Approve a PO (DRAFT -> APPROVED)."""
    organization = _organization(request)
    po = get_object_or_404(
        PurchaseOrder, pk=pk, organization=organization, status=PurchaseOrder.Status.DRAFT
    )
    
    po.status = PurchaseOrder.Status.APPROVED
    po.save()
    
    messages.success(request, f"Purchase Order {po.number} approved.")
    
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/po_status.html", {"po": po})
    return redirect("purchasing:po_detail", pk=pk)


@login_required
@permission_required(("purchasing", "purchaseorder", "change"))
@require_POST
def po_send(request, pk: int):
    """Send PO to vendor (APPROVED -> SENT)."""
    organization = _organization(request)
    po = get_object_or_404(
        PurchaseOrder, pk=pk, organization=organization, status=PurchaseOrder.Status.APPROVED
    )
    
    po.status = PurchaseOrder.Status.SENT
    po.save()
    
    messages.success(request, f"Purchase Order {po.number} sent to vendor.")
    
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/po_status.html", {"po": po})
    return redirect("purchasing:po_detail", pk=pk)


@login_required
@permission_required(("purchasing", "purchaseorder", "change"))
@require_POST
def po_cancel(request, pk: int):
    """Cancel a PO."""
    organization = _organization(request)
    po = get_object_or_404(PurchaseOrder, pk=pk, organization=organization)
    
    if po.status == PurchaseOrder.Status.CLOSED:
        messages.warning(request, "Closed purchase orders cannot be cancelled.")
        return redirect("purchasing:po_detail", pk=pk)
    
    po.status = PurchaseOrder.Status.CLOSED
    po.save()
    
    messages.success(request, f"Purchase Order {po.number} cancelled.")
    
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/po_status.html", {"po": po})
    return redirect("purchasing:po_detail", pk=pk)


# ============================================================================
# GOODS RECEIPT UNIFIED FLOW
# ============================================================================

@login_required
@permission_required(("purchasing", "goodsreceipt", "view"))
def gr_unified_form(request, pk: Optional[int] = None):
    """
    Unified Goods Receipt form with inline editable lines.
    Allows editing of received quantities, QC results, and batch tracking.
    """
    organization = _organization(request)
    gr = None
    
    if pk:
        gr = get_object_or_404(GoodsReceipt, pk=pk, organization=organization)
        required_action = "change"
    else:
        required_action = "add"
    
    if not PermissionUtils.has_permission(
        request.user, organization, "purchasing", "goodsreceipt", required_action
    ):
        raise PermissionDenied("You do not have permission to edit or create goods receipts.")
    
    form = GoodsReceiptForm(
        request.POST or None,
        instance=gr,
        organization=organization,
    )
    formset = GoodsReceiptLineFormSet(
        request.POST or None,
        instance=gr,
        prefix="lines",
        organization=organization,
    )
    
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                gr = form.save(commit=False)
                gr.organization = organization
                gr.status = GoodsReceipt.Status.DRAFT
                gr.save()
                formset.instance = gr
                formset.save()
            
            messages.success(
                request,
                f"Goods Receipt {gr.number} saved successfully."
            )
            return redirect("purchasing:gr_detail", pk=gr.id)
    
    form_action = (
        reverse("purchasing:gr_edit", kwargs={"pk": pk})
        if pk
        else reverse("purchasing:gr_unified_create")
    )
    
    context = {
        "form": form,
        "line_formset": formset,
        "form_action": form_action,
        "is_edit": bool(pk),
        "page_title": "Edit Goods Receipt" if pk else "New Goods Receipt",
        "form_title": "Goods Receipt",
        "breadcrumbs": [
            ("Purchasing", reverse("purchasing:gr_table")),
            ("Goods Receipt", None)
        ],
        "document_type": "goods_receipt",
    }
    return render(request, "purchasing/unified_form.html", context)


@login_required
@permission_required(("purchasing", "goodsreceipt", "change"))
@require_POST
def gr_inspect(request, pk: int):
    """Mark GR as inspected (RECEIVED -> INSPECTED)."""
    organization = _organization(request)
    gr = get_object_or_404(
        GoodsReceipt,
        pk=pk,
        organization=organization,
        status=GoodsReceipt.Status.DRAFT
    )
    
    gr.status = GoodsReceipt.Status.RECEIVED
    gr.save()
    
    messages.success(request, f"Goods Receipt {gr.number} marked as received.")
    
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/gr_status.html", {"gr": gr})
    return redirect("purchasing:gr_detail", pk=pk)


@login_required
@permission_required(("purchasing", "goodsreceipt", "change"))
@require_POST
def gr_post(request, pk: int):
    """Post GR to inventory and GL (INSPECTED -> POSTED)."""
    organization = _organization(request)
    gr = get_object_or_404(GoodsReceipt, pk=pk, organization=organization)
    
    try:
        post_goods_receipt(gr, user=request.user)
        messages.success(request, f"Goods Receipt {gr.number} posted successfully.")
    except ProcurementPostingError as exc:
        messages.error(request, f"Failed to post: {str(exc)}")
        return redirect("purchasing:gr_detail", pk=pk)
    
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/gr_status.html", {"gr": gr})
    return redirect("purchasing:gr_detail", pk=pk)


@login_required
@permission_required(("purchasing", "goodsreceipt", "delete"))
@require_POST
def gr_cancel(request, pk: int):
    """Cancel a GR."""
    organization = _organization(request)
    gr = get_object_or_404(GoodsReceipt, pk=pk, organization=organization)
    
    if gr.status == GoodsReceipt.Status.POSTED:
        messages.warning(request, "Posted receipts cannot be cancelled.")
        return redirect("purchasing:gr_detail", pk=pk)
    
    gr.status = GoodsReceipt.Status.CANCELLED
    gr.save()
    
    messages.success(request, f"Goods Receipt {gr.number} cancelled.")
    
    if getattr(request, "htmx", False):
        return render(request, "purchasing/partials/gr_status.html", {"gr": gr})
    return redirect("purchasing:gr_detail", pk=pk)


# ============================================================================
# LANDED COST UNIFIED FLOW
# ============================================================================

@login_required
@permission_required(("purchasing", "purchaseinvoice", "view"))
def landed_cost_unified_form(request, invoice_id: int, doc_id: Optional[int] = None):
    """
    Unified Landed Cost form with editable cost lines and auto-allocation.
    Allocates costs to invoice lines based on value or quantity.
    """
    organization = _organization(request)
    
    from purchasing.models import PurchaseInvoice
    invoice = get_object_or_404(
        PurchaseInvoice,
        pk=invoice_id,
        organization=organization
    )
    
    doc = None
    if doc_id:
        doc = get_object_or_404(
            LandedCostDocument,
            pk=doc_id,
            purchase_invoice=invoice
        )
    
    form = LandedCostDocumentForm(
        request.POST or None,
        instance=doc,
    )
    formset = LandedCostLineFormSet(
        request.POST or None,
        instance=doc,
        prefix="costs",
        organization=organization,
    )
    
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                doc = form.save(commit=False)
                doc.organization = organization
                doc.purchase_invoice = invoice
                doc.save()
                formset.instance = doc
                formset.save()
            
            messages.success(
                request,
                "Landed cost document saved. You can now allocate to line items."
            )
            return redirect("purchasing:landed-cost-allocate", doc_id=doc.id)
    
    # Calculate totals from invoice lines
    line_data = []
    total_value = Decimal("0")
    total_qty = Decimal("0")
    
    for line in invoice.lines.all():
        line_value = line.quantity * line.unit_price
        line_data.append({
            "line": line,
            "value": line_value,
            "qty": line.quantity,
        })
        total_value += line_value
        total_qty += line.quantity
    
    context = {
        "invoice": invoice,
        "doc": doc,
        "form": form,
        "cost_formset": formset,
        "line_data": line_data,
        "total_value": total_value,
        "total_qty": total_qty,
        "page_title": "Landed Cost",
        "form_title": "Landed Cost Allocation",
        "breadcrumbs": [
            ("Purchasing", reverse("purchasing:invoice-table")),
            ("Invoice", reverse("purchasing:invoice-detail", kwargs={"pk": invoice.id})),
            ("Landed Cost", None)
        ],
    }
    return render(request, "purchasing/landed_cost_form.html", context)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "change"))
@require_POST
def landed_cost_allocate(request, doc_id: int):
    """
    Auto-allocate landed costs to invoice lines based on allocation basis
    (value or quantity).
    """
    organization = _organization(request)
    doc = get_object_or_404(
        LandedCostDocument,
        pk=doc_id,
        purchase_invoice__organization=organization
    )
    
    try:
        apply_landed_cost_document(doc, request.user)
        messages.success(request, "Landed costs allocated successfully.")
    except ProcurementPostingError as exc:
        messages.error(request, f"Failed to allocate: {str(exc)}")
    
    return redirect("purchasing:invoice-detail", pk=doc.purchase_invoice.id)


@login_required
@permission_required(("purchasing", "purchaseinvoice", "delete"))
@require_POST
def landed_cost_delete(request, doc_id: int):
    """Delete a landed cost document."""
    organization = _organization(request)
    doc = get_object_or_404(
        LandedCostDocument,
        pk=doc_id,
        purchase_invoice__organization=organization
    )
    
    if doc.is_applied:
        messages.warning(request, "Applied landed cost documents cannot be deleted.")
        return redirect("purchasing:invoice-detail", pk=doc.purchase_invoice.id)
    
    invoice_id = doc.purchase_invoice.id
    doc.delete()
    
    messages.success(request, "Landed cost document deleted.")
    return redirect("purchasing:invoice-detail", pk=invoice_id)


# ============================================================================
# PURCHASE RETURN UNIFIED FLOW (via voucher system or native model)
# ============================================================================

@login_required
@permission_required(("purchasing", "purchasereturn", "view"))
def pr_unified_form(request, pk: Optional[int] = None, from_invoice_id: Optional[int] = None):
    """
    Unified Purchase Return form for returning goods to supplier.
    Can be created from invoice or standalone.
    """
    organization = _organization(request)
    
    # For now, this integrates with the invoice reverse flow
    # In future, could have dedicated PurchaseReturn model
    
    if from_invoice_id:
        from purchasing.models import PurchaseInvoice
        invoice = get_object_or_404(
            PurchaseInvoice,
            pk=from_invoice_id,
            organization=organization
        )
        
        if request.method == "POST":
            try:
                from purchasing.services import reverse_purchase_invoice
                reverse_purchase_invoice(invoice, user=request.user)
                messages.success(request, f"Invoice {invoice.number} return processed.")
                return redirect("purchasing:invoice-detail", pk=invoice.id)
            except ProcurementPostingError as exc:
                messages.error(request, f"Failed to return: {str(exc)}")
        
        context = {
            "invoice": invoice,
            "page_title": f"Return Invoice {invoice.number}",
            "action": "return",
        }
        return render(request, "purchasing/purchase_return_form.html", context)
    
    # Standalone return (future enhancement)
    messages.warning(request, "Standalone purchase returns coming soon.")
    return redirect("purchasing:invoice-table")


# ============================================================================
# LIST AND DETAIL VIEWS
# ============================================================================

@login_required
@permission_required(("purchasing", "purchaseorder", "view"))
def po_detail(request, pk: int):
    """Display PO detail with line items and actions."""
    organization = _organization(request)
    po = get_object_or_404(
        PurchaseOrder.objects.select_related("vendor", "currency"),
        pk=pk,
        organization=organization,
    )
    
    lines = po.lines.select_related("product").all()
    total_received = sum(
        (line.quantity_received for line in lines),
        Decimal("0")
    )
    
    context = {
        "page_title": f"Purchase Order {po.number}",
        "po": po,
        "lines": lines,
        "total_received": total_received,
        "can_edit": po.status == PurchaseOrder.Status.DRAFT,
        "can_approve": po.status == PurchaseOrder.Status.DRAFT,
        "can_send": po.status == PurchaseOrder.Status.APPROVED,
        "can_cancel": po.status != PurchaseOrder.Status.CLOSED,
    }
    return render(request, "purchasing/po_detail_page.html", context)


@login_required
@permission_required(("purchasing", "goodsreceipt", "view"))
def gr_detail(request, pk: int):
    """Display GR detail with line items and 3-way match status."""
    organization = _organization(request)
    gr = get_object_or_404(
        GoodsReceipt.objects.select_related("purchase_order"),
        pk=pk,
        organization=organization,
    )
    
    lines = gr.lines.select_related("po_line__product").all()
    po = gr.purchase_order
    
    context = {
        "page_title": f"Goods Receipt {gr.number}",
        "gr": gr,
        "po": po,
        "lines": lines,
        "can_edit": gr.status == GoodsReceipt.Status.DRAFT,
        "can_receive": gr.status == GoodsReceipt.Status.DRAFT,
        "can_post": gr.status in (GoodsReceipt.Status.RECEIVED, GoodsReceipt.Status.INSPECTED),
        "can_cancel": gr.status != GoodsReceipt.Status.POSTED,
    }
    return render(request, "purchasing/gr_detail_page.html", context)
