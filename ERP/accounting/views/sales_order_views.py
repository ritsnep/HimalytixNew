from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

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
        form = SalesOrderForm(organization=organization, initial={"organization": organization})
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
