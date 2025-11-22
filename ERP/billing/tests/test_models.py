from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from usermanagement.models import Organization
from billing.models import InvoiceHeader, InvoiceLine, current_fiscal_year_code, quantize_amount
from billing.utils import compute_vat_and_total


class BillingModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", code="TEST", type="company")

    def test_invoice_sequence_and_immutability(self):
        invoice = InvoiceHeader.objects.create(
            tenant=self.org,
            invoice_date=timezone.now().date(),
            customer_name="Acme",
            customer_pan="123456789",
        )
        self.assertTrue(invoice.invoice_number.startswith(str(invoice.invoice_date.year)))
        with self.assertRaises(ValidationError):
            invoice.customer_name = "Changed"
            invoice.save()

    def test_line_totals_and_quantize(self):
        invoice = InvoiceHeader.objects.create(
            tenant=self.org,
            invoice_date=timezone.now().date(),
            customer_name="Acme",
            customer_pan="123456789",
        )
        line = InvoiceLine.objects.create(invoice=invoice, description="Item", quantity=2, unit_price=Decimal("100"), vat_rate=Decimal("13"))
        self.assertEqual(line.taxable_amount, Decimal("200.00"))
        self.assertEqual(line.vat_amount, Decimal("26.00"))
        self.assertEqual(line.line_total, Decimal("226.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal("226.00"))

    def test_compute_vat_util(self):
        vat, total = compute_vat_and_total(Decimal("100"), Decimal("13"))
        self.assertEqual(vat, Decimal("13.00"))
        self.assertEqual(total, Decimal("113.00"))
        self.assertEqual(current_fiscal_year_code(), str(timezone.now().year))
        self.assertEqual(quantize_amount(Decimal("1.005")), Decimal("1.01"))
