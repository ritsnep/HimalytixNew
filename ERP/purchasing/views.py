from __future__ import annotations

from typing import Optional

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from usermanagement.utils import PermissionUtils, permission_required

from purchasing.forms import (
    LandedCostDocumentForm,
    LandedCostLineFormSet,
    PurchaseInvoiceForm,
    PurchaseInvoiceLineFormSet,
)
from purchasing.models import LandedCostDocument, PurchaseInvoice
from purchasing.services import (
    ProcurementPostingError,
    apply_landed_cost_document,
    post_purchase_invoice,
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
def invoice_detail(request, pk: int):
    organization = _organization(request)
    invoice = get_object_or_404(
        PurchaseInvoice.objects.select_related("supplier", "currency"),
        pk=pk,
        organization=organization,
    )
    return _render_invoice_detail(request, invoice)


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
            response = _render_invoice_detail(
                request,
                invoice,
                alert="Purchase invoice saved.",
            )
            response["HX-Trigger"] = "purchaseInvoiceChanged"
            return response
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
    }
    return render(request, "purchasing/partials/invoice_form.html", context)


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
            response = _render_invoice_detail(
                request,
                invoice,
                alert="Landed cost saved.",
            )
            response["HX-Trigger"] = "landedCostChanged"
            return response
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
    }
    return render(request, "purchasing/partials/landed_cost_form.html", context)


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
