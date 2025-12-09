from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.db.models import F, Sum, DecimalField, ExpressionWrapper, Q
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from accounting.forms import PaymentSchedulerForm
from accounting.models import PaymentBatch, PurchaseInvoice
from accounting.services.app_payment_service import APPaymentService, PaymentAllocation
from accounting.views.views_mixins import AccountsPayablePermissionMixin


class PaymentSchedulerView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/payment_scheduler.html"
    OPEN_STATUSES = ('validated', 'matched', 'ready_for_posting', 'posted')

    def get(self, request):
        organization = self.get_organization()
        form = PaymentSchedulerForm(
            organization=organization,
            initial={'scheduled_date': timezone.now().date()},
        )
        context = self._build_context(organization, form, [], Decimal("0"), [])
        return render(request, self.template_name, context)

    def post(self, request):
        organization = self.get_organization()
        form = PaymentSchedulerForm(request.POST, organization=organization)
        invoices = self._open_invoices(organization)
        selected_ids = request.POST.getlist("selected_invoices")
        selected_invoices = []
        if selected_ids:
            valid_ids = [int(value) for value in selected_ids if value.isdigit()]
            selected_invoices = list(invoices.filter(invoice_id__in=valid_ids))

        if not selected_invoices:
            form.add_error(None, "Select at least one invoice to schedule for payment.")
            context = self._build_context(
                organization,
                form,
                invoices,
                Decimal("0"),
                selected_ids,
            )
            return render(request, self.template_name, context)

        if not form.is_valid():
            context = self._build_context(
                organization,
                form,
                invoices,
                sum(inv.outstanding for inv in selected_invoices),
                selected_ids,
            )
            return render(request, self.template_name, context)

        total_selected = sum(inv.outstanding for inv in selected_invoices)
        batch = PaymentBatch.objects.create(
            organization=organization,
            batch_number=form.cleaned_data["batch_number"],
            scheduled_date=form.cleaned_data["scheduled_date"],
            currency=form.cleaned_data["currency"],
            status="scheduled",
            total_amount=total_selected,
            metadata={"notes": form.cleaned_data.get("notes") or ""},
            created_by=request.user,
            updated_by=request.user,
        )

        service = APPaymentService(request.user)
        invoices_by_vendor: dict[int, list[PurchaseInvoice]] = defaultdict(list)
        for invoice in selected_invoices:
            invoices_by_vendor[invoice.vendor_id].append(invoice)

        payments_created = []
        for idx, (vendor_id, vendor_invoices) in enumerate(invoices_by_vendor.items(), start=1):
            vendor = vendor_invoices[0].vendor
            payment_number = f"{batch.batch_number}-{vendor.code or vendor.vendor_id}-{idx}"
            allocations = [
                PaymentAllocation(invoice=invoice, amount=invoice.outstanding)
                for invoice in vendor_invoices
            ]
            try:
                payment = service.create_payment(
                    organization=organization,
                    vendor=vendor,
                    payment_number=payment_number,
                    payment_date=form.cleaned_data["scheduled_date"],
                    bank_account=form.cleaned_data["bank_account"],
                    currency=form.cleaned_data["currency"],
                    exchange_rate=form.cleaned_data["exchange_rate"],
                    allocations=allocations,
                    payment_method=form.cleaned_data["payment_method"],
                    batch=batch,
                )
            except Exception as exc:
                form.add_error(None, f"Unable to create payment for {vendor.display_name}: {exc}")
                batch.delete()
                context = self._build_context(
                    organization,
                    form,
                    invoices,
                    total_selected,
                    selected_ids,
                )
                return render(request, self.template_name, context)
            payments_created.append(payment)

        batch.total_amount = total_selected
        batch.save(update_fields=["total_amount"])

        messages.success(
            request,
            f"Scheduled {len(payments_created)} payment(s) totaling {total_selected:.2f} in batch {batch.batch_number}.",
        )
        return redirect(reverse("accounting:payment_scheduler"))

    def _build_context(self, organization, form, invoices, selected_total, selected_ids):
        return {
            "form": form,
            "invoices": invoices,
            "selected_total": selected_total,
            "selected_ids": selected_ids,
        }

    def _open_invoices(self, organization):
        settled_statuses = PurchaseInvoice.PAYMENT_SETTLED_STATUSES
        settled_filter = Q(payment_lines__payment__status__in=settled_statuses)
        invoices = (
            PurchaseInvoice.objects.filter(
                organization=organization,
                status__in=self.OPEN_STATUSES,
            )
            .select_related("vendor", "currency")
            .annotate(
                paid_amount=Coalesce(
                    Sum("payment_lines__applied_amount", filter=settled_filter),
                    Decimal("0"),
                ),
                discount_amount=Coalesce(
                    Sum("payment_lines__discount_taken", filter=settled_filter),
                    Decimal("0"),
                ),
            )
            .annotate(
                outstanding=ExpressionWrapper(
                    F("total") - F("paid_amount") - F("discount_amount"),
                    output_field=DecimalField(max_digits=19, decimal_places=4),
                )
            )
            .filter(outstanding__gt=Decimal("0"))
            .order_by("due_date", "invoice_number")
        )
        return invoices
