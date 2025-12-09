from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from django.db import models
from inventory.models import InventoryItem, Product

from accounting.forms import SalesOrderForm, SalesOrderLineForm
from accounting.mixins import PermissionRequiredMixin
from accounting.models import SalesOrder, SalesOrderLine
from accounting.services.sales_order_service import SalesOrderService


SalesOrderLineFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderLine,
    form=SalesOrderLineForm,
    extra=1,
    can_delete=True,
)


class SalesOrderListView(PermissionRequiredMixin, ListView):
    model = SalesOrder
    template_name = "accounting/sales_order_list.html"
    context_object_name = "orders"
    permission_required = ("accounting", "salesorder", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return SalesOrder.objects.none()
        return (
            SalesOrder.objects.filter(organization=organization)
            .select_related("customer")
            .order_by("-order_date", "-order_id")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:sales_order_create")
        context["create_button_text"] = "New Sales Order"
        return context


class SalesOrderCreateView(PermissionRequiredMixin, View):
    template_name = "accounting/sales_order_form.html"
    permission_required = ("accounting", "salesorder", "add")

    def get(self, request):
        organization = self.get_organization()
        form = SalesOrderForm(
            organization=organization,
            initial={"organization": organization, "warehouse": getattr(request.user, "default_warehouse", None)},
        )
        formset = SalesOrderLineFormSet(prefix="lines")
        context = self._build_context(form, formset)
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        form = SalesOrderForm(data=request.POST, organization=organization)
        formset = SalesOrderLineFormSet(request.POST, prefix="lines")
        context = self._build_context(form, formset)
        if organization:
            data = form.data.copy()
            data["organization"] = str(organization.pk)
            form.data = data
            form.instance.organization = organization
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
                }
            )

        service = SalesOrderService(request.user)
        try:
            service.create_order(
                organization=organization,
                customer=form.cleaned_data["customer"],
                warehouse=form.cleaned_data.get("warehouse"),
                currency=form.cleaned_data["currency"],
                order_date=form.cleaned_data.get("order_date"),
                expected_ship_date=form.cleaned_data.get("expected_ship_date"),
                exchange_rate=form.cleaned_data.get("exchange_rate") or Decimal("1"),
                reference_number=form.cleaned_data.get("reference_number"),
                notes=form.cleaned_data.get("notes"),
                metadata={},
                lines=line_payload,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, self.template_name, context)

        messages.success(request, "Sales order saved as draft.")
        return redirect(reverse("accounting:sales_order_list"))

    def _build_context(self, form, formset):
        return {
            "form": form,
            "line_formset": formset,
            "formset": formset,
            "form_title": "New Sales Order",
            "back_url": "accounting:sales_order_list",
        }


class SalesOrderActionView(PermissionRequiredMixin, View):
    """Handle confirm/convert actions for a sales order."""

    permission_required = ("accounting", "salesorder", "change")

    def post(self, request, pk):
        organization = self.get_organization()
        order = get_object_or_404(SalesOrder, pk=pk, organization=organization)
        action = request.POST.get("action")
        service = SalesOrderService(request.user)

        try:
            if action == "confirm":
                _, summary = service.confirm_order(order, warehouse=order.warehouse)
                if summary.get("shortages"):
                    shortage_text = ", ".join(
                        f"{item['product_code'] or 'N/A'} ({item['allocated']}/{item['requested']})"
                        for item in summary["shortages"]
                    )
                    messages.warning(request, f"Order confirmed with shortages: {shortage_text}")
                else:
                    messages.success(request, "Sales order confirmed and stock allocated.")
            elif action == "invoice":
                if order.status not in {"confirmed", "fulfilled"}:
                    raise ValidationError("Only confirmed or fulfilled orders can be invoiced.")
                invoice = service.convert_to_invoice(
                    order,
                    invoice_date=request.POST.get("invoice_date") or order.order_date,
                    payment_term=getattr(order.customer, "payment_term", None),
                    due_date=None,
                    warehouse=order.warehouse,
                    post_invoice=False,
                )
                messages.success(
                    request,
                    f"Converted to invoice {invoice.invoice_number or invoice.id}. Post the invoice to deduct stock.",
                )
            else:
                messages.error(request, "Unknown action for sales order.")
        except ValidationError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("accounting:sales_order_list"))


class SalesOrderAvailabilityHXView(PermissionRequiredMixin, View):
    """HTMX endpoint to fetch available quantity for a product/warehouse."""

    permission_required = ("accounting", "salesorder", "view")

    def get(self, request):
        organization = self.get_organization()
        product_code = request.GET.get("product_code", "").strip()
        if not product_code:
            # Formset names (e.g., lines-0-product_code)
            for key, value in request.GET.items():
                if key.endswith("product_code"):
                    product_code = value.strip()
                    break
        warehouse_id = request.GET.get("warehouse")
        warehouse = None
        if warehouse_id:
            from inventory.models import Warehouse

            warehouse = get_object_or_404(
                Warehouse,
                pk=warehouse_id,
                organization=organization,
            )
        product = Product.objects.filter(organization=organization, code=product_code).first()
        if not product:
            return render(request, "accounting/htmx/sales_order_availability.html", {"message": "Product not found"})

        qs = InventoryItem.objects.filter(organization=organization, product=product)
        if warehouse:
            qs = qs.filter(warehouse=warehouse)
        available_qty = qs.aggregate(total=models.Sum("quantity_on_hand"))
        quantity = available_qty.get("total") or Decimal("0")
        return render(
            request,
            "accounting/htmx/sales_order_availability.html",
            {"product": product, "quantity": quantity, "warehouse": warehouse},
        )
