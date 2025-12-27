from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    APPayment,
    APPaymentLine,
    Journal,
    JournalLine,
    PaymentApproval,
    PaymentBatch,
    PurchaseInvoice,
    Vendor,
)
from accounting.services.posting_service import PostingService
from accounting.utils.event_utils import emit_integration_event


@dataclass
class PaymentAllocation:
    invoice: PurchaseInvoice
    amount: Decimal
    discount: Decimal = Decimal('0')


class APPaymentService:
    """Handles AP payment scheduling, approval, and execution."""

    def __init__(self, user):
        self.user = user
        self.posting_service = PostingService(user)

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------
    @transaction.atomic
    def create_batch(self, *, organization, batch_number, scheduled_date, currency, metadata=None) -> PaymentBatch:
        batch = PaymentBatch.objects.create(
            organization=organization,
            batch_number=batch_number,
            scheduled_date=scheduled_date,
            currency=currency,
            status='draft',
            metadata=metadata or {},
            created_by=self.user,
            updated_by=self.user,
        )
        return batch

    # ------------------------------------------------------------------
    # Payment creation
    # ------------------------------------------------------------------
    @transaction.atomic
    def create_payment(
        self,
        *,
        organization,
        vendor: Vendor,
        payment_number: str,
        payment_date,
        bank_account,
        currency,
        exchange_rate: Decimal,
        allocations: Iterable[PaymentAllocation],
        payment_method: str = 'bank_transfer',
        batch: PaymentBatch | None = None,
    ) -> APPayment:
        total = sum((alloc.amount + alloc.discount) for alloc in allocations)
        if total <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        for alloc in allocations:
            outstanding = alloc.invoice.outstanding_amount(include_pending=True)
            if alloc.amount > outstanding:
                raise ValidationError(
                    f"Payment for invoice {alloc.invoice.invoice_number} exceeds outstanding balance ({alloc.amount} > {outstanding})."
                )

        payment = APPayment.objects.create(
            organization=organization,
            vendor=vendor,
            payment_number=payment_number,
            payment_date=payment_date,
            payment_method=payment_method,
            bank_account=bank_account,
            currency=currency,
            exchange_rate=exchange_rate,
            amount=total,
            status='draft',
            batch=batch,
            created_by=self.user,
            updated_by=self.user,
        )

        for alloc in allocations:
            if alloc.invoice.vendor_id != vendor.pk:
                raise ValidationError("All allocations must target the same vendor.")
            APPaymentLine.objects.create(
                payment=payment,
                invoice=alloc.invoice,
                applied_amount=alloc.amount,
                discount_taken=alloc.discount,
            )

        if batch:
            batch.recompute_total()

        return payment

    @transaction.atomic
    def approve_payment(self, payment: APPayment, approver, notes: str = '') -> APPayment:
        if payment.status not in {'draft'}:
            raise ValidationError("Only draft payments can be approved.")
        payment.status = 'approved'
        payment.updated_by = self.user
        payment.save(update_fields=['status', 'updated_by', 'updated_at'])
        PaymentApproval.objects.create(
            payment=payment,
            approver=approver,
            status='approved',
            notes=notes,
            decided_at=timezone.now(),
        )
        return payment

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    @transaction.atomic
    def execute_payment(self, payment: APPayment, journal_type, *, idempotency_key: str | None = None) -> APPayment:
        if payment.status not in {'approved', 'draft'}:
            raise ValidationError("Only draft or approved payments can be executed.")
        vendor_account = payment.vendor.accounts_payable_account
        if vendor_account is None:
            raise ValidationError("Vendor is missing an Accounts Payable account.")
        # Currency alignment: bank account currency (if present) must match payment currency
        bank_currency = getattr(payment.bank_account, "currency", None)
        bank_currency_id = getattr(bank_currency, "pk", None)
        if bank_currency_id and payment.currency_id and bank_currency_id != payment.currency.pk:
            raise ValidationError("Bank account currency must match payment currency.")

        period = AccountingPeriod.get_current_period(payment.organization)
        if not period:
            raise ValidationError("No open accounting period is available for posting.")

        journal = Journal.objects.create(
            organization=payment.organization,
            journal_type=journal_type,
            period=period,
            journal_date=payment.payment_date,
            description=f"Vendor payment {payment.payment_number} for {payment.vendor.display_name}",
            currency_code=payment.currency.currency_code,
            exchange_rate=payment.exchange_rate,
            status='draft',
            created_by=self.user,
            updated_by=self.user,
        )

        JournalLine.objects.create(
            journal=journal,
            line_number=1,
            account=vendor_account,
            description=f"Payment to {payment.vendor.display_name}",
            debit_amount=payment.amount,
            created_by=self.user,
        )
        JournalLine.objects.create(
            journal=journal,
            line_number=2,
            account=payment.bank_account,
            description="Cash/Bank credit",
            credit_amount=payment.amount,
            created_by=self.user,
        )

        from accounting.services.post_journal import post_journal
        posted = post_journal(journal, user=self.user, idempotency_key=idempotency_key)
        payment.status = 'executed'
        payment.journal = posted
        payment.updated_by = self.user
        payment.save(update_fields=['status', 'journal', 'updated_by', 'updated_at'])
        if payment.batch:
            payment.batch.status = 'processed'
            payment.batch.updated_by = self.user
            payment.batch.save(update_fields=['status', 'updated_by', 'updated_at'])
        invoice_ids = payment.lines.values_list('invoice_id', flat=True).distinct()
        invoices = PurchaseInvoice.objects.filter(invoice_id__in=invoice_ids)
        for invoice in invoices:
            invoice.refresh_payment_status()
        if payment.vendor_id:
            payment.vendor.recompute_outstanding_balance()
        emit_integration_event(
            'ap_payment_executed',
            payment,
            {
                'payment_number': payment.payment_number,
                'vendor': payment.vendor.display_name,
                'amount': str(payment.amount),
            },
        )
        return payment
