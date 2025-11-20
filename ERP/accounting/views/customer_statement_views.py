import csv
import logging
from decimal import Decimal
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from accounting.forms import CustomerStatementFilterForm
from accounting.models import SalesInvoice, ARReceipt
from accounting.views.views_mixins import AccountsReceivablePermissionMixin

logger = logging.getLogger(__name__)


class CustomerStatementView(AccountsReceivablePermissionMixin, View):
    template_name = "accounting/customer_statement.html"
    permission_required = ('accounting', 'salesinvoice', 'view')

    def get(self, request):
        organization = self.get_organization()
        form = CustomerStatementFilterForm(
            data=request.GET or None,
            organization=organization,
        )
        context = {
            "form": form,
            "statement": None,
        }

        if form.is_valid():
            customer = form.cleaned_data["customer"]
            start_date = form.cleaned_data["start_date"]
            end_date = form.cleaned_data["end_date"]
            invoices = self._invoice_rows(organization, customer, start_date, end_date)
            payments = self._payment_rows(organization, customer, start_date, end_date)
            totals = self._totals(invoices, payments)
            context["statement"] = {
                "customer": customer,
                "invoices": invoices,
                "payments": payments,
                "totals": totals,
                "start_date": start_date,
                "end_date": end_date,
            }
            if request.GET.get("export") == "csv":
                return self._export_csv(
                    request, customer, invoices, payments, totals, start_date, end_date
                )

        return render(request, self.template_name, context)

    def _invoice_rows(self, organization, customer, start_date, end_date):
        invoices = (
            SalesInvoice.objects.filter(
                organization=organization,
                customer=customer,
                invoice_date__range=(start_date, end_date),
            )
            .annotate(
                paid_amount=Coalesce(Sum("receipt_lines__applied_amount"), Decimal("0")),
                discount_amount=Coalesce(Sum("receipt_lines__discount_taken"), Decimal("0")),
            )
            .annotate(
                outstanding=F("total") - F("paid_amount") - F("discount_amount")
            )
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

    def _payment_rows(self, organization, customer, start_date, end_date):
        receipts = ARReceipt.objects.filter(
            organization=organization,
            customer=customer,
            receipt_date__range=(start_date, end_date),
        ).order_by("-receipt_date")
        rows = []
        for receipt in receipts:
            rows.append(
                {
                    "receipt_number": receipt.receipt_number,
                    "receipt_date": receipt.receipt_date,
                    "amount": receipt.amount,
                    "method": receipt.payment_method,
                    "reference": receipt.reference,
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

    def _export_csv(self, request, customer, invoices, payments, totals, start_date, end_date):
        filename = f"customer-statement-{customer.code or customer.customer_id}-{start_date}-{end_date}.csv"
        csv_data = self._build_csv_data(customer, invoices, payments, totals, start_date, end_date)
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        email_sent = self._send_statement_email(
            request, customer, csv_data, filename, start_date, end_date
        )
        response["X-Statement-Email"] = "sent" if email_sent else "not-sent"
        if email_sent:
            messages.info(
                request,
                f"Customer statement emailed to {customer.email or 'configured recipients'}.",
            )
        else:
            messages.info(request, "Customer statement exported (email not sent).")
        return response

    def _build_csv_data(self, customer, invoices, payments, totals, start_date, end_date):
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Customer", customer.display_name])
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
        writer.writerow(["Receipt #", "Date", "Amount", "Method", "Reference"])
        for payment in payments:
            writer.writerow(
                [
                    payment["receipt_number"],
                    payment["receipt_date"],
                    payment["amount"],
                    payment["method"],
                    payment["reference"],
                ]
            )
        writer.writerow([])
        writer.writerow(["Totals"])
        writer.writerow(["Invoiced", "Paid", "Outstanding", "Receipts", "Balance"])
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
        self, request, customer, csv_data, filename, start_date, end_date
    ) -> bool:
        if not customer.email:
            return False
        recipients = [customer.email]
        if request.user.email:
            recipients.append(request.user.email)
        subject = f"Customer statement {start_date} – {end_date}"
        body = (
            f"Attached is the customer statement for {customer.display_name} "
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
            logger.exception("Failed to send customer statement email.")
            return False
