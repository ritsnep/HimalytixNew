"""
Views for Purchase Order operations.

Provides CRUD operations and status management for purchase orders.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.decorators import permission_required, login_required
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from purchasing.models import PurchaseOrder, PurchaseOrderLine
from purchasing.services.purchase_order_service import PurchaseOrderService
from purchasing.forms import PurchaseOrderForm, PurchaseOrderLineForm
from accounting.models import Vendor


def _get_active_org(request):
    """Return the active organization or raise if missing."""
    getter = getattr(request.user, "get_active_organization", None)
    org = getter() if getter else getattr(request.user, "organization", None)
    if not org:
        raise PermissionDenied("Active organization is required to manage purchase orders.")
    setattr(request, "organization", org)
    if hasattr(request.user, "set_active_organization"):
        request.user.set_active_organization(org)
    return org


@method_decorator(login_required, name="dispatch")
class POWorkspaceView(View):
    """
    Split-panel workspace for purchase order management.
    Left: List of POs with search/filter
    Right: Detail/form panel
    """
    
    template_name = "purchasing/po_workspace.html"
    
    def get(self, request):
        organization = _get_active_org(request)
        
        # Get list context
        pos = PurchaseOrder.objects.filter(organization=organization).order_by("-created_at")
        
        # Apply filters from query string
        status_filter = request.GET.get("status")
        vendor_filter = request.GET.get("vendor")
        search = request.GET.get("search", "").strip()
        
        if status_filter:
            pos = pos.filter(status=status_filter)
        if vendor_filter:
            pos = pos.filter(vendor_id=vendor_filter)
        if search:
            pos = pos.filter(
                Q(number__icontains=search) |
                Q(vendor__display_name__icontains=search)
            )
        
        # Get selected PO for detail panel
        po_id = request.GET.get("po_id")
        selected_po = None
        if po_id:
            selected_po = get_object_or_404(PurchaseOrder, id=po_id, organization=organization)
        
        context = {
            "pos": pos[:50],  # Paginate in real app
            "selected_po": selected_po,
            "status_choices": PurchaseOrder.Status.choices,
            "vendors": Vendor.objects.filter(organization=organization),
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.view_purchaseorder"), name="dispatch")
class POListView(ListView):
    """List all purchase orders for organization."""
    
    model = PurchaseOrder
    template_name = "purchasing/po_list.html"
    context_object_name = "pos"
    paginate_by = 50
    
    def get_queryset(self):
        organization = _get_active_org(self.request)
        qs = PurchaseOrder.objects.filter(organization=organization).order_by("-created_at")
        
        # Apply filters
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        
        search = self.request.GET.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(number__icontains=search) |
                Q(vendor__display_name__icontains=search)
            )
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = PurchaseOrder.Status.choices
        return context


class POListPageView(POListView):
    """Full-page list using Dason list base."""

    template_name = "purchasing/po_list_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Purchase Orders",
                "create_url": reverse("purchasing:po_unified_create"),
                "create_button_text": "New Purchase Order",
            }
        )
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.view_purchaseorder"), name="dispatch")
class PODetailView(DetailView):
    """View purchase order details."""
    
    model = PurchaseOrder
    template_name = "purchasing/po_detail.html"
    context_object_name = "po"
    
    def get_queryset(self):
        return PurchaseOrder.objects.filter(organization=_get_active_org(self.request))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        po = self.object
        
        # Add summary data
        context["line_count"] = po.lines.count()
        context["total_qty"] = po.lines.aggregate(Sum("quantity_ordered"))["quantity_ordered__sum"] or 0
        context["qty_received"] = po.lines.aggregate(Sum("quantity_received"))["quantity_received__sum"] or 0
        
        # Calculate 3-way match status
        context["po_lines"] = po.lines.all()
        context["line_form"] = PurchaseOrderLineForm(organization=_get_active_org(self.request))
        
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.add_purchaseorder"), name="dispatch")
class POCreateView(CreateView):
    """Create a new purchase order."""
    
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "purchasing/po_form.html"
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = _get_active_org(self.request)
        return kwargs
    
    def form_valid(self, form):
        organization = _get_active_org(self.request)
        vendor = form.cleaned_data["vendor"]
        
        # Get line items from formset
        # This would be handled via AJAX in HTMX app
        # For now, create minimal PO
        service = PurchaseOrderService(self.request.user)
        
        try:
            po = service.create_purchase_order(
                organization=organization,
                vendor=vendor,
                lines=[],  # Will be added via update
                order_date=form.cleaned_data.get("order_date", timezone.now().date()),
                currency=form.cleaned_data.get("currency"),
                due_date=form.cleaned_data.get("due_date"),
            )
            
            return redirect("po_detail", pk=po.id)
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Create Purchase Order",
                "form_title": "Purchase Order",
                "breadcrumbs": [("Purchasing", reverse("purchasing:po_table")), ("New PO", None)],
            }
        )
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_purchaseorder"), name="dispatch")
class POUpdateView(UpdateView):
    """Update a purchase order (draft only)."""
    
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "purchasing/po_form.html"
    
    def get_queryset(self):
        organization = _get_active_org(self.request)
        return PurchaseOrder.objects.filter(organization=organization, status=PurchaseOrder.Status.DRAFT)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = _get_active_org(self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Edit Purchase Order",
                "form_title": "Purchase Order",
                "breadcrumbs": [("Purchasing", reverse("purchasing:po_table")), ("Edit PO", None)],
            }
        )
        return context
    
    def form_valid(self, form):
        po = self.object
        
        # Update via service to maintain integrity
        service = PurchaseOrderService(self.request.user)
        po.vendor = form.cleaned_data["vendor"]
        po.due_date = form.cleaned_data.get("due_date")
        po.currency = form.cleaned_data.get("currency")
        po.notes = form.cleaned_data.get("notes", "")
        po.save()
        
        return redirect("po_detail", pk=po.id)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_purchaseorder"), name="dispatch")
class POApproveView(View):
    """Approve a purchase order (DRAFT -> APPROVED)."""
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        po = get_object_or_404(PurchaseOrder, id=pk, organization=organization, status=PurchaseOrder.Status.DRAFT)
        
        service = PurchaseOrderService(request.user)
        try:
            po = service.approve_purchase_order(po)
            
            if request.headers.get("HX-Request"):
                return render(request, "purchasing/partials/po_detail.html", {"po": po})
            return redirect("po_detail", pk=po.id)
        except ValidationError as e:
            if request.headers.get("HX-Request"):
                return JsonResponse({"error": str(e)}, status=400)
            return redirect("po_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_purchaseorder"), name="dispatch")
class POSendView(View):
    """Send PO to vendor (APPROVED -> SENT)."""
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        po = get_object_or_404(PurchaseOrder, id=pk, organization=organization, status=PurchaseOrder.Status.APPROVED)
        
        service = PurchaseOrderService(request.user)
        try:
            po = service.mark_sent(po)
            
            if request.headers.get("HX-Request"):
                return render(request, "purchasing/partials/po_detail.html", {"po": po})
            return redirect("po_detail", pk=po.id)
        except ValidationError as e:
            if request.headers.get("HX-Request"):
                return JsonResponse({"error": str(e)}, status=400)
            return redirect("po_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.change_purchaseorder"), name="dispatch")
class POCancelView(View):
    """Cancel a purchase order."""
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        po = get_object_or_404(PurchaseOrder, id=pk, organization=organization)
        
        service = PurchaseOrderService(request.user)
        try:
            po = service.cancel_purchase_order(po)
            
            if request.headers.get("HX-Request"):
                return render(request, "purchasing/partials/po_detail.html", {"po": po})
            return redirect("po_detail", pk=po.id)
        except ValidationError as e:
            if request.headers.get("HX-Request"):
                return JsonResponse({"error": str(e)}, status=400)
            return redirect("po_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("purchasing.add_purchaseorderline"), name="dispatch")
class POLineAddView(View):
    """Add a line item to a PO (AJAX)."""
    
    def post(self, request, pk):
        organization = _get_active_org(request)
        po = get_object_or_404(PurchaseOrder, id=pk, organization=organization, status=PurchaseOrder.Status.DRAFT)
        
        # Get line data from POST
        try:
            form = PurchaseOrderLineForm(request.POST, organization=organization)
            
            if form.is_valid():
                line = form.save(commit=False)
                line.purchase_order = po
                line.save()
                
                # Recalculate PO totals
                po.recalc_totals()
                po.save()
                
                if request.headers.get("HX-Request"):
                    return render(request, "purchasing/partials/po_line.html", {"line": line, "po": po})
                return JsonResponse({"id": line.id, "status": "created"})
            else:
                return JsonResponse({"errors": form.errors}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
