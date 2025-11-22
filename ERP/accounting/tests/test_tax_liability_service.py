from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import Customer, PurchaseInvoice, SalesInvoice, Vendor
from accounting.tests import factories
from accounting.services.tax_liability_service import TaxLiabilityService


class TaxLiabilityServiceTests(TestCase):
    def setUp(self):
        self.org = factories.create_organization(name='TaxOrg', code='TAX')
        self.currency = factories.create_currency()
        self.expense_account = factories.create_chart_of_account(
            organization=self.org,
            account_type=factories.create_account_type(nature='expense'),
            currency=self.currency,
        )
        self.revenue_account = factories.create_chart_of_account(
            organization=self.org,
            account_type=factories.create_account_type(nature='income'),
            currency=self.currency,
        )
        self.ap_account = factories.create_chart_of_account(
            organization=self.org,
            account_type=factories.create_account_type(nature='liability'),
            currency=self.currency,
        )
        self.ar_account = factories.create_chart_of_account(
            organization=self.org,
            account_type=factories.create_account_type(nature='asset'),
            currency=self.currency,
        )
        self.tax_code = factories.create_tax_code(organization=self.org)
        self.tax_code.tax_rate = Decimal('0.10')
        self.tax_code.rate = Decimal('0.10')
        self.tax_code.save(update_fields=['tax_rate', 'rate'])
        self.customer = Customer.objects.create(
            organization=self.org,
            code='CUST1',
            display_name='Customer One',
            accounts_receivable_account=self.ar_account,
            revenue_account=self.revenue_account,
        )
        self.vendor = Vendor.objects.create(
            organization=self.org,
            code='VEND1',
            display_name='Vendor One',
            accounts_payable_account=self.ap_account,
            expense_account=self.expense_account,
        )

    def test_tax_service_aggregates_payable_and_receivable(self):
        period_start = date(2025, 1, 1)
        invoice = SalesInvoice.objects.create(
            organization=self.org,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
            invoice_number='SI-1',
            invoice_date=period_start,
            due_date=period_start,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('100'),
            tax_total=Decimal('10'),
            total=Decimal('110'),
            base_currency_total=Decimal('110'),
            status='posted',
        )
        invoice.lines.create(
            line_number=1,
            description='Sales',
            quantity=1,
            unit_price=Decimal('100'),
            revenue_account=self.revenue_account,
            tax_code=self.tax_code,
            tax_amount=Decimal('10'),
        )
        purchase_invoice = PurchaseInvoice.objects.create(
            organization=self.org,
            vendor=self.vendor,
            vendor_display_name=self.vendor.display_name,
            invoice_number='PI-1',
            invoice_date=period_start,
            due_date=period_start,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('50'),
            tax_total=Decimal('5'),
            total=Decimal('55'),
            base_currency_total=Decimal('55'),
            status='posted',
        )
        purchase_invoice.lines.create(
            line_number=1,
            description='Supplies',
            quantity=1,
            unit_cost=Decimal('50'),
            account=self.expense_account,
            tax_code=self.tax_code,
            tax_amount=Decimal('5'),
        )
        service = TaxLiabilityService(self.org)
        buckets = service.aggregate(period_start)
        self.assertEqual(len(buckets), 1)
        bucket = buckets[0]
        self.assertEqual(bucket.tax_code.pk, self.tax_code.pk)
        self.assertEqual(bucket.receivable, Decimal('10'))
        self.assertEqual(bucket.payable, Decimal('5'))
