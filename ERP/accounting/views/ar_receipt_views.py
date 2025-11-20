from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from accounting.forms import ARReceiptForm, ARReceiptLineForm
from accounting.mixins import PermissionRequiredMixin
from accounting.models import ARReceipt, ARReceiptLine, Customer, SalesInvoice
from accounting.services.sales_invoice_service import ReceiptAllocation, SalesInvoiceService


class BaseARReceiptLineFormSet(BaseInlineFormSet):
    """Inject organization/customer context into line forms."""

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        self.customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs["organization"] = self.organization
        kwargs["customer"] = self.customer
        return super()._construct_form(i, **kwargs)


ARReceiptLineFormSet = inlineformset_factory(
    ARReceipt,
    ARReceiptLine,
    form=ARReceiptLineForm,
    formset=BaseARReceiptLineFormSet,
    extra=1,
    can_delete=True,
)


class ARReceiptListView(PermissionRequiredMixin, ListView):
    model = ARReceipt
    template_name = "accounting/ar_receipt_list.html"
    context_object_name = "receipts"
    permission_required = ("accounting", "arreceipt", "view")

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return ARReceipt.objects.none()
        return (
            ARReceipt.objects.filter(organization=organization)
            .select_related("customer")
            .order_by("-receipt_date", "-receipt_id")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["create_url"] = reverse("accounting:ar_receipt_create")
        context["create_button_text"] = "New Receipt"
        return context


class ARReceiptCreateView(PermissionRequiredMixin, View):
    template_name = "accounting/ar_receipt_form.html"
    permission_required = ("accounting", "arreceipt", "add")

    def get(self, request):
        organization = self.get_organization()
        form = ARReceiptForm(
            organization=organization,
            initial={"organization": organization},
        )
        if organization:
            form.instance.organization = organization
        formset = self._build_formset(organization=organization, customer=None)
        context = self._build_context(form, formset)
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        customer = self._get_customer_from_request(organization, request.POST.get("customer"))
        form = ARReceiptForm(
            data=request.POST,
            organization=organization,
        )
        if organization:
            form.instance.organization = organization
        formset = self._build_formset(
            organization=organization,
            customer=customer,
            data=request.POST,
        )
        context = self._build_context(form, formset)

        if not (form.is_valid() and formset.is_valid()):
            return render(request, self.template_name, context)

        allocations, errors_present = self._build_allocations(formset)
        if errors_present:
            return render(request, self.template_name, context)

        if not allocations:
            form.add_error(None, "Add at least one invoice allocation.")
            return render(request, self.template_name, context)

        service = SalesInvoiceService(request.user)
        try:
            receipt = service.apply_receipt(
                organization=organization,
                customer=form.cleaned_data["customer"],
                receipt_number=form.cleaned_data["receipt_number"],
                receipt_date=form.cleaned_data["receipt_date"],
                currency=form.cleaned_data["currency"],
                exchange_rate=form.cleaned_data.get("exchange_rate") or Decimal("1"),
                amount=form.cleaned_data["amount"],
                payment_method=form.cleaned_data.get("payment_method") or "bank_transfer",
                reference=form.cleaned_data.get("reference") or "",
                allocations=allocations,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, self.template_name, context)

        messages.success(request, f"Receipt {receipt.receipt_number} recorded.")
        return redirect(reverse("accounting:ar_receipt_list"))

    def _build_formset(self, *, organization, customer, data=None):
        return ARReceiptLineFormSet(
            data=data or None,
            prefix="lines",
            organization=organization,
            customer=customer,
        )

    def _build_context(self, form, formset):
        return {
            "form": form,
            "line_formset": formset,
            "formset": formset,
            "form_title": "New Customer Receipt",
            "back_url": "accounting:ar_receipt_list",
        }

    def _get_customer_from_request(self, organization, customer_pk):
        if not organization or not customer_pk:
            return None
        try:
            return Customer.objects.get(pk=customer_pk, organization=organization)
        except Customer.DoesNotExist:
            return None

    def _build_allocations(self, formset):
        allocations: dict[SalesInvoice, ReceiptAllocation] = {}
        has_errors = False

        for form in formset.forms:
            if not form.has_changed() or form.cleaned_data.get("DELETE"):
                continue

            invoice = form.cleaned_data.get("invoice")
            applied_amount = form.cleaned_data.get("applied_amount") or Decimal("0")
            discount_taken = form.cleaned_data.get("discount_taken") or Decimal("0")

            if invoice is None:
                form.add_error("invoice", "Select an invoice to apply the receipt.")
                has_errors = True
                continue

            if applied_amount <= 0 and discount_taken <= 0:
                form.add_error("applied_amount", "Enter an amount or discount to apply.")
                has_errors = True
                continue

            if invoice in allocations:
                form.add_error("invoice", "Invoice already selected.")
                has_errors = True
                continue

            allocations[invoice] = ReceiptAllocation(
                amount=applied_amount,
                discount=discount_taken,
            )

        return allocations, has_errors
