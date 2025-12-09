import csv
import logging
from decimal import Decimal
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db.models import F, Sum, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from accounting.forms import VendorStatementFilterForm
from accounting.models import PurchaseInvoice, APPayment, Vendor
from accounting.views.views_mixins import AccountsPayablePermissionMixin

logger = logging.getLogger(__name__)


class VendorStatementView(AccountsPayablePermissionMixin, View):
    template_name = "accounting/vendor_statement.html"
    permission_tuple = ("accounting", "appayment", "view")

    def get(self, request):
        organization = self.get_organization()
        form = VendorStatementFilterForm(
            data=request.GET or None,
            organization=organization,
        )
        context = {
            "form": form,
            "statement": None,
        }

        if form.is_valid():
            vendor = form.cleaned_data["vendor"]
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            invoices = self._invoice_rows(organization, vendor, start_date, end_date)
            payments = self._payment_rows(organization, vendor, start_date, end_date)
            totals = self._totals(invoices, payments)
            context["statement"] = {
                "vendor": vendor,
                "invoices": invoices,
                "payments": payments,
                "totals": totals,
                "start_date": start_date,
                "end_date": end_date,
            }
            if request.GET.get("export") == "csv":
                return self._export_csv(
                    request, vendor, invoices, payments, totals, start_date, end_date
                )

        return render(request, self.template_name, context)

    def _invoice_rows(self, organization, vendor, start_date, end_date):
        settled_statuses = PurchaseInvoice.PAYMENT_SETTLED_STATUSES
        settled_filter = Q(payment_lines__payment__status__in=settled_statuses)
        invoices = (
            PurchaseInvoice.objects.filter(
                organization=organization,
                vendor=vendor,
                invoice_date__range=(start_date, end_date),
            )
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
            .annotate(outstanding=F("total") - F("paid_amount") - F("discount_amount"))
            .order_by("invoice_date")
        )
        rows = []
        for invoice in invoices:
            rows.append(
                {
                    "invoice_number": invoice.invoice_number,
                    "invoice_date": invoice.invoice_date,
                    "due_date": invoice.due_date,
                    "total": invoice.total,
                    "paid": invoice.paid_amount,
                    "discount": invoice.discount_amount,
                    "outstanding": invoice.outstanding,
                }
            )
        return rows

    def _payment_rows(self, organization, vendor, start_date, end_date):
        payments = APPayment.objects.filter(
            organization=organization,
            vendor=vendor,
            payment_date__range=(start_date, end_date),
        ).order_by("-payment_date")
        rows = []
        for payment in payments:
            rows.append(
                {
                    "payment_number": payment.payment_number,
                    "payment_date": payment.payment_date,
                    "amount": payment.amount,
                    "method": payment.payment_method,
                    "status": payment.status,
                }
            )
        return rows

    def _totals(self, invoices, payments):
        total_invoiced = sum(item["total"] for item in invoices)
        total_paid = sum(item["paid"] for item in invoices)
        total_outstanding = sum(item["outstanding"] for item in invoices)
        total_payments = sum(item["amount"] for item in payments)
        return {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "total_payments": total_payments,
            "statement_balance": total_invoiced - total_payments,
        }

    def _export_csv(self, request, vendor, invoices, payments, totals, start_date, end_date):
        filename = f"statement-{vendor.code or vendor.vendor_id}-{start_date}-{end_date}.csv"
        csv_data = self._build_csv_data(vendor, invoices, payments, totals, start_date, end_date)
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        email_sent = self._send_statement_email(
            request, vendor, csv_data, filename, start_date, end_date
        )
        response["X-Statement-Email"] = "sent" if email_sent else "not-sent"
        if email_sent:
            messages.info(
                request, f"Vendor statement emailed to {vendor.email} and copied to you (if configured)."
            )
        else:
            messages.info(
                request,
                "Vendor statement exported; no email was sent because the vendor lacks an address.",
            )
        return response

    def _build_csv_data(self, vendor, invoices, payments, totals, start_date, end_date):
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Vendor", vendor.display_name])
        writer.writerow(["Period", f"{start_date} to {end_date}"])
        writer.writerow([])
        writer.writerow(["Invoices"])
        writer.writerow(
            ["Invoice #", "Date", "Due Date", "Total", "Paid", "Discount", "Outstanding"]
        )
        for invoice in invoices:
            writer.writerow(
                [
                    invoice["invoice_number"],
                    invoice["invoice_date"],
                    invoice["due_date"],
                    invoice["total"],
                    invoice["paid"],
                    invoice["discount"],
                    invoice["outstanding"],
                ]
            )
        writer.writerow([])
        writer.writerow(["Payments"])
        writer.writerow(["Payment #", "Date", "Amount", "Method", "Status"])
        for payment in payments:
            writer.writerow(
                [
                    payment["payment_number"],
                    payment["payment_date"],
                    payment["amount"],
                    payment["method"],
                    payment["status"],
                ]
            )
        writer.writerow([])
        writer.writerow(["Totals"])
        writer.writerow(["Invoiced", "Paid", "Outstanding", "Payments", "Balance"])
        writer.writerow(
            [
                totals["total_invoiced"],
                totals["total_paid"],
                totals["total_outstanding"],
                totals["total_payments"],
                totals["statement_balance"],
            ]
        )
        return buffer.getvalue()

    def _send_statement_email(
        self, request, vendor, csv_data, filename, start_date, end_date
    ) -> bool:
        if not vendor.email:
            return False
        recipients = [vendor.email]
        if request.user.email:
            recipients.append(request.user.email)
        subject = f"Vendor statement {start_date} – {end_date}"
        body = (
            f"Attached is the vendor statement for {vendor.display_name} "
            f"covering {start_date} through {end_date}."
        )
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.attach(filename, csv_data, "text/csv")
        try:
            email.send(fail_silently=False)
            return True
        except Exception:
            logger.exception("Failed to send vendor statement email.")
            return False
