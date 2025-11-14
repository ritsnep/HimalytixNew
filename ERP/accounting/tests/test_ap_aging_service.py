from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from accounting.models import (
    AccountType,
    APPayment,
    APPaymentLine,
    ChartOfAccount,
    Currency,
    Organization,
    PaymentTerm,
    PurchaseInvoice,
    Vendor,
)
from accounting.services.ap_aging_service import APAgingService


class APAgingServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Aging Org',
            code='AGING',
            type='company',
        )
        self.currency = Currency.objects.create(
            currency_code='USD',
            currency_name='US Dollar',
            symbol='$',
        )
        liability_type = AccountType.objects.create(
            code='LIA200',
            name='Accounts Payable',
            nature='liability',
            classification='Statement of Financial Position',
            balance_sheet_category='Liabilities',
            income_statement_category=None,
            cash_flow_category='Operating Activities',
            display_order=1,
        )
        bank_type = AccountType.objects.create(
            code='AST200',
            name='Bank',
            nature='asset',
            classification='Statement of Financial Position',
            balance_sheet_category='Assets',
            income_statement_category=None,
            cash_flow_category='Operating Activities',
            display_order=2,
        )
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=liability_type,
            account_code='2005',
            account_name='AP Control',
            currency=self.currency,
        )
        self.bank_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=bank_type,
            account_code='1015',
            account_name='Main Bank',
            currency=self.currency,
        )
        self.payment_term = PaymentTerm.objects.create(
            organization=self.organization,
            code='NET30',
            name='Net 30',
            term_type='ap',
            net_due_days=30,
        )
        self.vendor = Vendor.objects.create(
            organization=self.organization,
            code='V-AGING',
            display_name='Aging Vendor',
            payment_term=self.payment_term,
            accounts_payable_account=self.ap_account,
            default_currency=self.currency,
        )
        self.reference_date = date(2025, 1, 31)

    def test_aging_buckets_respect_due_dates_and_payments(self):
        # Invoice 1 overdue by 10 days with partial payment
        invoice1 = PurchaseInvoice.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            vendor_display_name=self.vendor.display_name,
            invoice_number='AGING-PI-1',
            invoice_date=self.reference_date - timedelta(days=40),
            due_date=self.reference_date - timedelta(days=10),
            payment_term=self.payment_term,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('100'),
            tax_total=Decimal('0'),
            total=Decimal('100'),
            base_currency_total=Decimal('100'),
            status='posted',
        )

        payment = APPayment.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            payment_number='PAY-AGING-1',
            payment_date=self.reference_date - timedelta(days=5),
            payment_method='bank_transfer',
            bank_account=self.bank_account,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            amount=Decimal('40'),
            status='executed',
        )
        APPaymentLine.objects.create(
            payment=payment,
            invoice=invoice1,
            applied_amount=Decimal('40'),
            discount_taken=Decimal('0'),
        )

        # Invoice 2 still current
        PurchaseInvoice.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            vendor_display_name=self.vendor.display_name,
            invoice_number='AGING-PI-2',
            invoice_date=self.reference_date - timedelta(days=5),
            due_date=self.reference_date + timedelta(days=10),
            payment_term=self.payment_term,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=Decimal('200'),
            tax_total=Decimal('0'),
            total=Decimal('200'),
            base_currency_total=Decimal('200'),
            status='posted',
        )

        service = APAgingService(self.organization, reference_date=self.reference_date)
        rows = service.build()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.vendor_id, self.vendor.pk)
        self.assertEqual(row.buckets['01-30'], Decimal('60'))  # outstanding from invoice 1
        self.assertEqual(row.buckets['current'], Decimal('200'))
        self.assertEqual(row.total, Decimal('260'))

        summary = service.summarize()
        self.assertEqual(summary['01-30'], Decimal('60'))
        self.assertEqual(summary['current'], Decimal('200'))
