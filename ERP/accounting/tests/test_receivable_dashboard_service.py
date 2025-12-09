from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounting.models import (
    AccountType,
    ARReceipt,
    ARReceiptLine,
    ChartOfAccount,
    Currency,
    Customer,
    Organization,
    SalesInvoice,
)
from accounting.services.receivable_dashboard_service import ReceivableDashboardService


class ReceivableDashboardServiceTests(TestCase):
    def setUp(self):
        self.as_of_date = date(2025, 12, 9)
        self.organization = Organization.objects.create(name='Receivable Org', code='RECV', type='company')
        self.currency = Currency.objects.create(currency_code='USD', currency_name='US Dollar', symbol='$')
        self.account_type = AccountType.objects.create(
            code='AST001',
            name='Assets',
            nature='asset',
            classification='Statement of Financial Position',
            display_order=1,
        )
        self.ar_account = ChartOfAccount.objects.create(
            organization=self.organization,
            account_type=self.account_type,
            account_code='1200',
            account_name='Accounts Receivable',
            currency=self.currency,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            code='CUST001',
            display_name='Acme Co',
            accounts_receivable_account=self.ar_account,
            default_currency=self.currency,
        )

        self.invoice_current = self._create_invoice(
            'SI-001',
            invoice_date=date(2025, 11, 25),
            due_date=date(2025, 12, 10),
            total=Decimal('100'),
        )
        self.invoice_30_day = self._create_invoice(
            'SI-002',
            invoice_date=date(2025, 11, 1),
            due_date=date(2025, 11, 20),
            total=Decimal('200'),
        )
        self.invoice_90_day = self._create_invoice(
            'SI-003',
            invoice_date=date(2025, 9, 1),
            due_date=date(2025, 10, 1),
            total=Decimal('150'),
        )

        receipt = ARReceipt.objects.create(
            organization=self.organization,
            customer=self.customer,
            receipt_number='RCPT-1',
            receipt_date=date(2025, 12, 3),
            currency=self.currency,
            exchange_rate=Decimal('1'),
            amount=Decimal('45'),
        )
        ARReceiptLine.objects.create(
            receipt=receipt,
            invoice=self.invoice_current,
            applied_amount=Decimal('40'),
            discount_taken=Decimal('5'),
        )

        now = timezone.now()
        self.initial_reminder = SimpleNamespace(
            pk=1,
            invoice_id=self.invoice_current.pk,
            channel='email',
            status='sent',
            sent_at=now - timedelta(days=3),
            message='Initial reminder',
        )
        self.latest_reminder = SimpleNamespace(
            pk=2,
            invoice_id=self.invoice_current.pk,
            channel='email',
            status='sent',
            sent_at=now,
            message='Latest reminder',
        )

        class _ReminderQuerySet(list):  # simple stub replacing ORM queryset
            def order_by(self, *args, **kwargs):
                ordered = sorted(self, key=lambda r: r.sent_at or timezone.now(), reverse=True)
                return _ReminderQuerySet(ordered)

        self._reminder_patcher = patch(
            'accounting.services.receivable_dashboard_service.ReceivableReminder'
        )
        self.mock_reminder = self._reminder_patcher.start()
        reminders = _ReminderQuerySet([self.initial_reminder, self.latest_reminder])
        self.mock_reminder.objects.filter.return_value = reminders
        self.addCleanup(self._reminder_patcher.stop)

    def _create_invoice(self, number: str, invoice_date: date, due_date: date, total: Decimal) -> SalesInvoice:
        return SalesInvoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            customer_display_name=self.customer.display_name,
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
        service = ReceivableDashboardService(self.organization, as_of=self.as_of_date)
        rows = service.get_invoice_rows()

        self.assertEqual(len(rows), 3)

        buckets = service.bucket_summary(rows)
        self.assertEqual(buckets[0]['count'], 2)
        self.assertEqual(buckets[0]['total'], Decimal('255'))
        self.assertEqual(buckets[2]['count'], 1)
        self.assertEqual(buckets[2]['total'], Decimal('150'))

        grand = service.grand_total(rows)
        self.assertEqual(grand, Decimal('405'))

    def test_reminder_selection_picks_latest(self):
        service = ReceivableDashboardService(self.organization, as_of=self.as_of_date)
        rows = service.get_invoice_rows()
        current_row = next(row for row in rows if row['invoice_number'] == 'SI-001')
        self.assertIs(current_row['last_reminder'], self.latest_reminder)

    def test_serialization_helpers(self):
        service = ReceivableDashboardService(self.organization, as_of=self.as_of_date)
        rows = service.get_invoice_rows()
        serialized_rows = service.serialize_rows(rows)
        serialized_map = {row['invoice_number']: row for row in serialized_rows}

        self.assertEqual(serialized_map['SI-001']['outstanding'], 55.0)
        self.assertEqual(serialized_map['SI-001']['last_reminder']['id'], self.latest_reminder.pk)
        self.assertEqual(serialized_map['SI-001']['last_reminder']['message'], 'Latest reminder')

        buckets = service.bucket_summary(rows)
        serialized_buckets = service.serialize_buckets(buckets)
        self.assertEqual(serialized_buckets[0]['total'], 255.0)
        self.assertEqual(serialized_buckets[0]['count'], 2)