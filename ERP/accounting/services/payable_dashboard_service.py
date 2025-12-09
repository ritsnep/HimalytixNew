from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounting.models import PurchaseInvoice, PayableReminder

BUCKET_DEFINITIONS = [
    ("Current (0-30d)", 0, 30),
    ("31-60 days", 31, 60),
    ("61-90 days", 61, 90),
    (">90 days", 91, None),
]

OPEN_STATUSES = {'posted', 'validated', 'matched', 'ready_for_posting'}


def _decimal_coalesce(field: str):
    return Coalesce(Sum(field), Decimal('0'))


class PayableDashboardService:
    def __init__(self, organization, as_of: date | None = None):
        self.organization = organization
        self.as_of = as_of or timezone.localdate()

    def get_invoice_rows(self) -> List[Dict[str, object]]:
        invoices = (
            PurchaseInvoice.objects.filter(
                organization=self.organization,
                status__in=OPEN_STATUSES,
            )
            .annotate(
                applied=_decimal_coalesce('payment_lines__applied_amount'),
                discount=_decimal_coalesce('payment_lines__discount_taken'),
            )
            .select_related('vendor', 'currency')
            .order_by('due_date')
        )
        invoice_ids = [invoice.pk for invoice in invoices]
        reminders = {}
        for reminder in PayableReminder.objects.filter(invoice_id__in=invoice_ids, status='sent').order_by('-sent_at'):
            reminders.setdefault(reminder.invoice_id, reminder)

        rows: List[Dict[str, object]] = []
        for invoice in invoices:
            outstanding = (invoice.total or Decimal('0')) - (Decimal(invoice.applied) + Decimal(invoice.discount))
            days_overdue = self._calculate_overdue_days(invoice)
            if outstanding <= Decimal('0'):
                continue
            rows.append({
                'invoice': invoice,
                'invoice_number': invoice.invoice_number,
                'vendor': invoice.vendor_display_name,
                'due_date': invoice.due_date,
                'status': invoice.status,
                'currency': invoice.currency.currency_code if invoice.currency else '',
                'outstanding': outstanding,
                'days_overdue': days_overdue,
                'last_reminder': reminders.get(invoice.pk),
            })
        return rows

    def bucket_summary(self, rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
        buckets = [{'label': label, 'total': Decimal('0'), 'count': 0} for label, *_ in BUCKET_DEFINITIONS]
        for row in rows:
            days = row.get('days_overdue', 0)
            outstanding = row.get('outstanding') or Decimal('0')
            for index, (label, start, end) in enumerate(BUCKET_DEFINITIONS):
                if (days >= start) and (end is None or days <= end):
                    buckets[index]['total'] += outstanding
                    buckets[index]['count'] += 1
                    break
        return buckets

    def grand_total(self, rows: List[Dict[str, object]]) -> Decimal:
        return sum((row.get('outstanding') or Decimal('0')) for row in rows)

    def _calculate_overdue_days(self, invoice: PurchaseInvoice) -> int:
        if not invoice.due_date:
            return 0
        delta = (self.as_of - invoice.due_date).days
        return delta if delta > 0 else 0

    def serialize_rows(self, rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
        serialized = []
        for row in rows:
            reminder = row.get('last_reminder')
            reminder_payload = None
            if reminder:
                reminder_payload = {
                    'id': reminder.pk,
                    'sent_at': reminder.sent_at.isoformat() if reminder.sent_at else None,
                    'channel': reminder.channel,
                    'status': reminder.status,
                    'message': reminder.message,
                }
            due_date = row.get('due_date')
            serialized.append({
                'invoice_id': row['invoice'].invoice_id,
                'invoice_number': row['invoice_number'],
                'vendor': row['vendor'],
                'due_date': due_date.isoformat() if due_date else None,
                'status': row['status'],
                'currency': row['currency'],
                'outstanding': float(row['outstanding']),
                'days_overdue': row['days_overdue'],
                'last_reminder': reminder_payload,
            })
        return serialized

    def serialize_buckets(self, buckets: List[Dict[str, object]]) -> List[Dict[str, object]]:
        return [
            {
                'label': bucket['label'],
                'total': float(bucket['total']),
                'count': bucket['count'],
            }
            for bucket in buckets
        ]
