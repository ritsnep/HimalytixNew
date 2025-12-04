"""
Views for Goods Receipt operations.

Handles receipt workflow: Create GR -> Inspect -> Post to GL & Inventory.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import permission_required, login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from purchasing.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder
from purchasing.services.goods_receipt_service import GoodsReceiptService
from purchasing.services.matching_service import validate_3way_match
from purchasing.forms import GoodsReceiptForm


def _get_active_org(request):
    """Return the active organization or raise if missing."""
    getter = getattr(request.user, "get_active_organization", None)
    org = getter() if getter else getattr(request.user, "organization", None)
    if not org:
        raise PermissionDenied("Active organization is required to manage goods receipts.")
    setattr(request, "organization", org)
    if hasattr(request.user, "set_active_organization"):
        request.user.set_active_organization(org)
    return org


def _build_match_result(gr: GoodsReceipt):
    """Build 3-way match payload for a GR."""
    po = gr.purchase_order
    po_lines = [
        {
            "id": line.id,
            "quantity_ordered": line.quantity_ordered,
            "unit_price": line.unit_price,
        }
        for line in po.lines.all()
    ]
    gr_lines = [
        {
            "po_line_id": line.po_line_id,
            "quantity_accepted": line.quantity_accepted,
            "quantity_received": line.quantity_received,
        }
        for line in gr.lines.all()
    ]
    inv_lines = [
        {
            "po_line_id": line.id,
            "quantity_invoiced": line.quantity_invoiced,
            "unit_price": line.unit_price,
        }
        for line in po.lines.all()
    ]
    return validate_3way_match(po_lines, gr_lines, inv_lines)


@method_decorator(login_required, name="dispatch")
class GRWorkspaceView(View):
    """
    Split-panel workspace for goods receipt management.
    Left: List of GRs with search/filter
    Right: Detail/form panel
    """
    
    template_name = "purchasing/gr_workspace.html"
    
    def get(self, request):
        organization = _get_active_org(request)
        
        # Get list context
        grs = GoodsReceipt.objects.filter(organization=organization).order_by("-created_at")
        
        # Apply filters
        status_filter = request.GET.get("status")
        po_filter = request.GET.get("po")
        search = request.GET.get("search", "").strip()
        
        if status_filter:
            grs = grs.filter(status=status_filter)
        if po_filter:
            grs = grs.filter(purchase_order_id=po_filter)
        if search:
            grs = grs.filter(
                Q(number__icontains=search) |
                Q(purchase_order__number__icontains=search) |
                Q(purchase_order__vendor__display_name__icontains=search)
            )
        
        # Get selected GR for detail panel
        gr_id = request.GET.get("gr_id")
        selected_gr = None
        if gr_id:
            selected_gr = get_object_or_404(GoodsReceipt, id=gr_id, organization=organization)
        
        context = {
            "grs": grs[:50],  # Paginate in real app
            "selected_gr": selected_gr,
            "status_choices": GoodsReceipt.Status.choices,
            "pos": PurchaseOrder.objects.filter(organization=organization, status=PurchaseOrder.Status.SENT),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.view_goodsreceipt"), name="dispatch")
class GRListView(ListView):
    """List all goods receipts for organization."""
    
    model = GoodsReceipt
    template_name = "purchasing/gr_list.html"
    context_object_name = "grs"
    paginate_by = 50
    
    def get_queryset(self):
        organization = _get_active_org(self.request)
        qs = GoodsReceipt.objects.filter(organization=organization).order_by("-created_at")
        
        # Apply filters
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(number__icontains=search) |
                Q(purchase_order__number__icontains=search)
            )
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = GoodsReceipt.Status.choices
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.view_goodsreceipt"), name="dispatch")
class GRDetailView(DetailView):
    """View goods receipt details with line items and 3-way match status."""
    
    model = GoodsReceipt
    template_name = "purchasing/gr_detail.html"
    context_object_name = "gr"
    
    def get_queryset(self):
        return GoodsReceipt.objects.filter(organization=_get_active_org(self.request))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        gr = self.object
        po = gr.purchase_order
        
        # Add line summary
        context["line_count"] = gr.lines.count()
        context["total_received"] = gr.lines.aggregate(Sum("quantity_received"))["quantity_received__sum"] or 0
        context["total_accepted"] = gr.lines.aggregate(Sum("quantity_accepted"))["quantity_accepted__sum"] or 0
        
        context["match_result"] = validate_3way_match(
            po_lines=[
                {
                    "id": line.id,
                    "quantity_ordered": line.quantity_ordered,
                    "unit_price": line.unit_price,
                }
                for line in po.lines.all()
            ],
            gr_lines=[
                {
                    "po_line_id": line.po_line_id,
                    "quantity_accepted": line.quantity_accepted,
                    "quantity_received": line.quantity_received,
                }
                for line in gr.lines.all()
            ],
            inv_lines=[
                {
                    "po_line_id": line.id,
                    "quantity_invoiced": line.quantity_invoiced,
                    "unit_price": line.unit_price,
                }
                for line in po.lines.all()
            ],
        )
        
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.add_goodsreceipt"), name="dispatch")
class GRCreateView(CreateView):
    """Create a new goods receipt from a PO."""
    
    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = "purchasing/gr_form.html"
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = _get_active_org(self.request)
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Goods Receipt"
        
        # Get available POs
        organization = _get_active_org(self.request)
        context["pos"] = PurchaseOrder.objects.filter(
            organization=organization,
            status=PurchaseOrder.Status.SENT
        )
        
        return context
    
    def form_valid(self, form):
        organization = _get_active_org(self.request)
        po = form.cleaned_data["purchase_order"]
        warehouse = form.cleaned_data["warehouse"]
        
        # Validate PO belongs to org
        if po.organization != organization:
            form.add_error("purchase_order", "Invalid purchase order")
            return self.form_invalid(form)
        
        service = GoodsReceiptService(self.request.user)
        
        try:
            # Create line items from PO lines
            lines = []
            for po_line in po.lines.all():
                lines.append({
                    "po_line": po_line,
                    "quantity_received": 0,  # To be filled in detail view
                    "quantity_accepted": 0,
                })
            
            gr = service.create_goods_receipt(
                purchase_order=po,
                warehouse=warehouse,
                lines=lines,
                receipt_date=form.cleaned_data.get("receipt_date", timezone.now().date()),
                reference_number=form.cleaned_data.get("reference_number", ""),
            )
            
            return redirect("gr_detail", pk=gr.id)
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_goodsreceipt"), name="dispatch")
class GRUpdateView(UpdateView):
    """Update a goods receipt (draft only)."""
    
    model = GoodsReceipt
    form_class = GoodsReceiptForm
    template_name = "purchasing/gr_form.html"
    
    def get_queryset(self):
        organization = _get_active_org(self.request)
        return GoodsReceipt.objects.filter(
            organization=organization,
            status=GoodsReceipt.Status.DRAFT
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = _get_active_org(self.request)
        return kwargs
    
    def form_valid(self, form):
        gr = self.object
        
        gr.warehouse = form.cleaned_data["warehouse"]
        gr.receipt_date = form.cleaned_data.get("receipt_date", gr.receipt_date)
        gr.reference_number = form.cleaned_data.get("reference_number", "")
        gr.notes = form.cleaned_data.get("notes", "")
        gr.save()
        
        return redirect("gr_detail", pk=gr.id)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_goodsreceipt"), name="dispatch")
class GRPostView(View):
    """
    Post GR to GL and Inventory.
    Creates journal entry and stock ledger entries.
    """
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        gr = get_object_or_404(
            GoodsReceipt,
            id=pk,
            organization=organization,
            status=GoodsReceipt.Status.DRAFT
        )

        # 3-way match check before posting
        match_result = validate_3way_match(
            po_lines=[
                {"id": line.id, "quantity_ordered": line.quantity_ordered, "unit_price": line.unit_price}
                for line in gr.purchase_order.lines.all()
            ],
            gr_lines=[
                {
                    "po_line_id": line.po_line_id,
                    "quantity_accepted": line.quantity_accepted,
                    "quantity_received": line.quantity_received,
                }
                for line in gr.lines.all()
            ],
            inv_lines=[
                {
                    "po_line_id": line.id,
                    "quantity_invoiced": line.quantity_invoiced,
                    "unit_price": line.unit_price,
                }
                for line in gr.purchase_order.lines.all()
            ],
        )
        if match_result["status"] == "fail":
            message = "Cannot post GR: 3-way match failed. Resolve variances first."
            if request.headers.get("HX-Request"):
                return JsonResponse({"error": message, "match": match_result}, status=400)
            messages.error(request, message)
            return redirect("gr_detail", pk=pk)
        
        service = GoodsReceiptService(request.user)
        try:
            gr = service.post_goods_receipt(gr)
            
            if request.headers.get("HX-Request"):
                return render(request, "purchasing/partials/gr_detail.html", {"gr": gr})
            
            return redirect("gr_detail", pk=gr.id)
        except ValidationError as e:
            if request.headers.get("HX-Request"):
                return JsonResponse({"error": str(e)}, status=400)
            return redirect("gr_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_goodsreceipt"), name="dispatch")
class GRCancelView(View):
    """Cancel a goods receipt."""
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        gr = get_object_or_404(GoodsReceipt, id=pk, organization=organization)
        
        service = GoodsReceiptService(request.user)
        try:
            gr = service.cancel_goods_receipt(gr)
            
            if request.headers.get("HX-Request"):
                return render(request, "purchasing/partials/gr_detail.html", {"gr": gr})
            return redirect("gr_detail", pk=gr.id)
        except ValidationError as e:
            if request.headers.get("HX-Request"):
                return JsonResponse({"error": str(e)}, status=400)
            return redirect("gr_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.add_goodsreceiptline"), name="dispatch")
class GRLineUpdateView(View):
    """Update GR line item quantities (AJAX)."""
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        gr_line = get_object_or_404(
            GoodsReceiptLine,
            id=pk,
            receipt__organization=organization,
        )
        
        gr = gr_line.receipt
        if gr.status != GoodsReceipt.Status.DRAFT:
            return JsonResponse({"error": "Cannot modify posted GR"}, status=400)
        
        try:
            qty_received_raw = request.POST.get("quantity_received", "0")
            qty_accepted_raw = request.POST.get("quantity_accepted", qty_received_raw)
            qty_received = Decimal(str(qty_received_raw or "0"))
            qty_accepted = Decimal(str(qty_accepted_raw or qty_received_raw or "0"))
            if qty_received < 0 or qty_accepted < 0:
                return JsonResponse({"error": "Quantities cannot be negative."}, status=400)
            
            # Validate
            if qty_accepted > qty_received:
                return JsonResponse(
                    {"error": "Accepted qty cannot exceed received qty"},
                    status=400
                )
            
            po_qty_remaining = gr_line.po_line.quantity_ordered - gr_line.po_line.quantity_received
            if qty_received > po_qty_remaining:
                return JsonResponse(
                    {"error": f"Cannot receive more than {po_qty_remaining} units"},
                    status=400
                )
            
            gr_line.quantity_received = qty_received.quantize(Decimal("0.0001"))
            gr_line.quantity_accepted = qty_accepted.quantize(Decimal("0.0001"))
            gr_line.save()
            
            if request.headers.get("HX-Request"):
                return render(request, "purchasing/partials/gr_line.html", {"line": gr_line})
            
            return JsonResponse({"status": "updated"})
        except (InvalidOperation, ValueError) as e:
            return JsonResponse({"error": "Invalid quantity input."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
