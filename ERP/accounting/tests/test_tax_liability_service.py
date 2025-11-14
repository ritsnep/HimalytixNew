from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountType,
    ChartOfAccount,
    Currency,
    Organization,
    PurchaseInvoice,
    SalesInvoice,
    TaxCode,
)
from accounting.services.tax_liability_service import TaxLiabilityService


class TaxLiabilityServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='TaxOrg', code='TAX', type='company')
        self.currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar', symbol='$')
        self.account_type = AccountType.objects.create(
            code='EXP200',
            name='Expense',
            nature='expense',
            classification='Statement of Profit or Loss',
            balance_sheet_category=None,
            income_statement_category='Expense',
            cash_flow_category='Operating Activities',
            display_order=1,
        )
        self.account = ChartOfAccount.objects.create(
            organization=self.org,
            account_type=self.account_type,
            account_code='5001',
            account_name='Taxable Expense',
            currency=self.currency,
        )
        self.tax_code = TaxCode.objects.create(
            organization=self.org,
            code='TX1',
            name='VAT',
            tax_type_id=1,
            tax_rate=Decimal('0.10'),
            rate=Decimal('0.10'),
        )

    def test_tax_service_aggregates_payable_and_receivable(self):
        period_start = date(2025, 1, 1)
        SalesInvoice.objects.create(
            organization=self.org,
            customer_id=1,
            customer_display_name='Acct',
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
        ).lines.create(
            line_number=1,
            account=self.account,
            description='Sales',
            currency=self.currency,
            debit_amount=0,
            credit_amount=110,
            tax_code=self.tax_code,
            tax_amount=Decimal('10'),
        )
        service = TaxLiabilityService(self.org)
        buckets = service.aggregate(period_start)
        self.assertEqual(len(buckets), 1)
        bucket = buckets[0]
        self.assertEqual(bucket.tax_code.pk, self.tax_code.pk)
        self.assertEqual(bucket.receivable, Decimal('10'))
        self.assertEqual(bucket.payable, Decimal('0'))
