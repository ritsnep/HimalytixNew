from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounting.models import (
    AccountType,
    APPayment,
    APPaymentLine,
    ChartOfAccount,
    Currency,
    Organization,
    PaymentTerm,
    PayableReminder,
    PurchaseInvoice,
    Vendor,
)
from accounting.services.payable_dashboard_service import PayableDashboardService


class PayableDashboardServiceTests(TestCase):
    def setUp(self):
        self.as_of_date = date(2025, 12, 9)
        self.organization = Organization.objects.create(name='Payable Org', code='PAY', type='company')
        self.currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar', symbol='$')
        self.account_type = AccountType.objects.create(
            code='LIAB001',
            name='Liabilities',
            nature='liability',
            classification='Statement of Financial Position',
            display_order=1,
        )
        self.ap_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            account_code='2000',
            account_name='Accounts Payable',
            currency=self.currency,
        )
        self.bank_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            account_code='1010',
            account_name='Bank Account',
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
            code='VEND001',
            display_name='Acme Supplies',
            accounts_payable_account=self.ap_account,
            default_currency=self.currency,
            payment_term=self.payment_term,
        )

        self.invoice_current = self._create_invoice(
            'PI-001',
            invoice_date=date(2025, 11, 25),
            due_date=date(2025, 12, 10),
            total=Decimal('100'),
        )
        self.invoice_30_day = self._create_invoice(
            'PI-002',
            invoice_date=date(2025, 11, 1),
            due_date=date(2025, 11, 1),
            total=Decimal('200'),
        )
        self.invoice_90_day = self._create_invoice(
            'PI-003',
            invoice_date=date(2025, 9, 1),
            due_date=date(2025, 9, 5),
            total=Decimal('150'),
        )

        payment = APPayment.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            payment_number='PAY-1',
            payment_date=date(2025, 12, 5),
            currency=self.currency,
            exchange_rate=Decimal('1'),
            amount=Decimal('50'),
            status='executed',
            bank_account=self.bank_account,
        )
        APPaymentLine.objects.create(
            payment=payment,
            invoice=self.invoice_current,
            applied_amount=Decimal('25'),
            discount_taken=Decimal('5'),
        )

        now = timezone.now()
        PayableReminder.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            invoice=self.invoice_current,
            channel='email',
            status='sent',
            sent_at=now - timedelta(days=2),
            message='First reminder',
        )
        PayableReminder.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            invoice=self.invoice_current,
            channel='sms',
            status='sent',
            sent_at=now,
            message='Latest reminder',
        )

    def _create_invoice(self, number: str, invoice_date: date, due_date: date, total: Decimal) -> PurchaseInvoice:
        return PurchaseInvoice.objects.create(
            organization=self.organization,
            vendor=self.vendor,
            vendor_display_name=self.vendor.display_name,
            invoice_number=number,
            invoice_date=invoice_date,
            due_date=due_date,
            currency=self.currency,
            exchange_rate=Decimal('1'),
            subtotal=total,
            tax_total=Decimal('0'),
            total=total,
            base_currency_total=total,
            status='posted',
        )

    def test_bucket_summary_and_grand_total(self):
        service = PayableDashboardService(self.organization, as_of=self.as_of_date)
        rows = service.get_invoice_rows()

        self.assertEqual(len(rows), 3)

        buckets = service.bucket_summary(rows)
        self.assertEqual(buckets[0]['count'], 1)
        self.assertEqual(buckets[0]['total'], Decimal('70'))
        self.assertEqual(buckets[1]['count'], 1)
        self.assertEqual(buckets[1]['total'], Decimal('200'))
        self.assertEqual(buckets[3]['count'], 1)
        self.assertEqual(buckets[3]['total'], Decimal('150'))

        grand = service.grand_total(rows)
        self.assertEqual(grand, Decimal('420'))

    def test_reminder_selection_picks_latest(self):
        service = PayableDashboardService(self.organization, as_of=self.as_of_date)
        rows = service.get_invoice_rows()
        current_row = next(row for row in rows if row['invoice_number'] == 'PI-001')
        self.assertEqual(current_row['last_reminder'].message, 'Latest reminder')

    def test_serialization_helpers(self):
        service = PayableDashboardService(self.organization, as_of=self.as_of_date)
        rows = service.get_invoice_rows()
        serialized = service.serialize_rows(rows)
        current_serialized = next(item for item in serialized if item['invoice_number'] == 'PI-001')

        self.assertEqual(current_serialized['outstanding'], 70.0)
        self.assertEqual(current_serialized['vendor'], self.vendor.display_name)
        self.assertEqual(current_serialized['last_reminder']['channel'], 'sms')

        buckets = service.bucket_summary(rows)
        serialized_buckets = service.serialize_buckets(buckets)
        self.assertEqual(serialized_buckets[0]['total'], 70.0)
        self.assertEqual(serialized_buckets[0]['count'], 1)
