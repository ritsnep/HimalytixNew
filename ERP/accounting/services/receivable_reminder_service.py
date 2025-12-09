from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounting.models import (
    ReceivableReminder,
    REMINDER_CHANNEL_EMAIL,
    REMINDER_CHANNEL_SMS,
    SalesInvoice,
)

logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    TWILIO_AVAILABLE = False
    TwilioClient = None  # type: ignore[assignment]


class ReceivableReminderService:
    def __init__(self, user=None):
        self.user = user
        self.logger = logger

    def queue_reminders(
        self,
        *,
        invoices: Iterable[SalesInvoice],
        channel: str = REMINDER_CHANNEL_EMAIL,
        message_template: str | None = None,
    ) -> list[ReceivableReminder]:
        queued = []
        now = timezone.now()
        for invoice in invoices:
            outstanding = self._outstanding_amount(invoice)
            if outstanding <= Decimal('0'):
                continue

            message = message_template or self._default_message(invoice, channel, outstanding)
            reminder = ReceivableReminder.objects.create(
                organization=invoice.organization,
                customer=invoice.customer,
                invoice=invoice,
                channel=channel,
                message=message,
                scheduled_at=now,
                created_by=self.user,
                updated_by=self.user,
            )
            queued.append(reminder)
            # Delay sending via Celery task to keep UI responsive
            try:
                from accounting.tasks import send_receivable_reminder

                send_receivable_reminder.apply_async((reminder.pk,))
            except Exception as exc:  # pragma: no cover - celery may not be available
                self.logger.warning("reminder.queue.failure", exc_info=exc)
        return queued

    def queue_overdue_reminders(self, *, as_of: date | None = None) -> list[ReceivableReminder]:
        as_of = as_of or timezone.localdate()
        threshold = int(getattr(settings, 'AR_REMINDER_AUTO_THRESHOLD_DAYS', 7))
        bucket_days = max(threshold, 1)
        cutoff = as_of - timedelta(days=bucket_days)
        channel = getattr(settings, 'AR_REMINDER_AUTO_CHANNEL', REMINDER_CHANNEL_EMAIL)
        template = getattr(settings, 'AR_REMINDER_AUTO_MESSAGE', None)

        invoices = (
            SalesInvoice.objects.filter(
                organization__isnull=False,
                status__in=['posted', 'validated'],
                due_date__lte=cutoff,
            )
            .annotate(
                applied=DecimalSum('receipt_lines__applied_amount'),
                discount=DecimalSum('receipt_lines__discount_taken'),
            )
            .select_related('customer')
        )
        overdue = [inv for inv in invoices if self._outstanding_amount(inv) > Decimal('0')]
        return self.queue_reminders(invoices=overdue, channel=channel, message_template=template)

    def deliver(self, reminder: ReceivableReminder) -> dict[str, object]:
        if reminder.channel == REMINDER_CHANNEL_EMAIL:
            return self._send_email(reminder)
        if reminder.channel == REMINDER_CHANNEL_SMS:
            return self._send_sms(reminder)
        raise ValueError(f"Unsupported reminder channel: {reminder.channel}")

    def _default_message(self, invoice: SalesInvoice, channel: str, outstanding: Decimal) -> str:
        days = invoice.days_overdue() if hasattr(invoice, 'days_overdue') else 0
        return (
            f"Friendly reminder - invoice {invoice.invoice_number} "
            f"for {invoice.customer_display_name} is overdue by {days} days. "
            f"Amount outstanding: {invoice.currency.code if invoice.currency else ''} {outstanding:.2f}."
        )

    def _send_email(self, reminder: ReceivableReminder) -> dict[str, object]:
        recipient = reminder.customer.email
        if not recipient:
            raise ValueError("Customer has no email address configured.")
        subject = getattr(
            settings,
            'AR_REMINDER_EMAIL_SUBJECT',
            f"Payment reminder for invoice {reminder.invoice.invoice_number if reminder.invoice else ''}",
        )
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', settings.SERVER_EMAIL)
        send_mail(subject, reminder.message, from_email, [recipient])
        return {'sent_to': recipient}

    def _send_sms(self, reminder: ReceivableReminder) -> dict[str, object]:
        if not TWILIO_AVAILABLE:
            raise RuntimeError("Twilio client is not installed.")
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        from_number = getattr(settings, 'TWILIO_FROM_NUMBER', '')
        if not (account_sid and auth_token and from_number):
            raise ValueError("Twilio is not configured.")
        recipient = reminder.customer.phone_number
        if not recipient:
            raise ValueError("Customer has no phone number configured.")
        client = TwilioClient(account_sid, auth_token)
        message = client.messages.create(
            body=reminder.message,
            from_=from_number,
            to=recipient,
        )
        return {'sid': getattr(message, 'sid', ''), 'sent_to': recipient}

    @staticmethod
    def _outstanding_amount(invoice: SalesInvoice) -> Decimal:
        applied = getattr(invoice, 'applied', None)
        discount = getattr(invoice, 'discount', None)
        if applied is None or discount is None:
            aggregates = invoice.receipt_lines.aggregate(
                applied=Coalesce(Sum('applied_amount'), Decimal('0')),  # type: ignore[name-defined]
                discount=Coalesce(Sum('discount_taken'), Decimal('0')),  # type: ignore[name-defined]
            )
            applied = aggregates['applied']
            discount = aggregates['discount']
        subtotal = invoice.total or Decimal('0')
        return subtotal - (Decimal(applied or Decimal('0')) + Decimal(discount or Decimal('0')))


def DecimalSum(field_name: str):
    return Coalesce(Sum(field_name), Decimal('0'))  # type: ignore[return-value]