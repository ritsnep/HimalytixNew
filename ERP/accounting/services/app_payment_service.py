from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, List, Dict, Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

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

logger = logging.getLogger(__name__)
User = get_user_model()


@dataclass
class PaymentAllocation:
    invoice: PurchaseInvoice
    amount: Decimal
    discount: Decimal = Decimal('0')


@dataclass
class BulkOperationResult:
    """Result of bulk operation with success/failure tracking."""
    successful: List[APPayment]
    failed: List[Dict[str, Any]]
    total_count: int


class APPaymentService:
    """Handles AP payment scheduling, approval, execution, reconciliation, and cancellation."""

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
    def approve_payment(self, payment: APPayment, approver=None, notes: str = '') -> APPayment:
        """Approve a payment for execution."""
        if payment.status not in {'draft'}:
            raise ValidationError("Only draft payments can be approved.")
        if not approver:
            approver = self.user

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
        
        logger.info(f"Payment {payment.payment_number} approved by {approver.username}")
        return payment

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    @transaction.atomic
    def execute_payment(self, payment: APPayment, journal_type, *, idempotency_key: str | None = None) -> APPayment:
        """Execute a payment and post the corresponding journal entries."""
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
        
        # Update invoice payment status
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
        
        logger.info(f"Payment {payment.payment_number} executed successfully")
        return payment

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------
    @transaction.atomic
    def reconcile_payment(self, payment: APPayment, notes: str = '') -> APPayment:
        """Reconcile an executed payment (mark as fully reconciled)."""
        if payment.status != 'executed':
            raise ValidationError("Only executed payments can be reconciled.")
        
        if not payment.journal or payment.journal.status != 'posted':
            raise ValidationError("Payment must have a posted journal to be reconciled.")
        
        payment.status = 'reconciled'
        payment.updated_by = self.user
        payment.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        emit_integration_event(
            'ap_payment_reconciled',
            payment,
            {
                'payment_number': payment.payment_number,
                'vendor': payment.vendor.display_name,
                'amount': str(payment.amount),
                'notes': notes,
            },
        )
        
        logger.info(f"Payment {payment.payment_number} reconciled by {self.user.username}")
        return payment

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------
    @transaction.atomic
    def cancel_payment(self, payment: APPayment, reason: str = '') -> APPayment:
        """Cancel a payment (only allowed for draft or approved payments)."""
        if payment.status not in {'draft', 'approved'}:
            raise ValidationError("Only draft or approved payments can be cancelled.")
        
        payment.status = 'cancelled'
        payment.updated_by = self.user
        payment.save(update_fields=['status', 'updated_by', 'updated_at'])
        
        # If there's a journal, mark it as reversed
        if payment.journal:
            payment.journal.is_reversal = True
            payment.journal.status = 'reversed'
            payment.journal.updated_by = self.user
            payment.journal.save(update_fields=['is_reversal', 'status', 'updated_by', 'updated_at'])
        
        emit_integration_event(
            'ap_payment_cancelled',
            payment,
            {
                'payment_number': payment.payment_number,
                'vendor': payment.vendor.display_name,
                'amount': str(payment.amount),
                'reason': reason,
            },
        )
        
        logger.info(f"Payment {payment.payment_number} cancelled by {self.user.username}. Reason: {reason}")
        return payment

    # ------------------------------------------------------------------
    # Bulk Operations
    # ------------------------------------------------------------------
    def bulk_approve_payments(self, payment_ids: List[int], approver=None, notes: str = '') -> BulkOperationResult:
        """Bulk approve multiple payments."""
        if not approver:
            approver = self.user
            
        result = BulkOperationResult(successful=[], failed=[], total_count=len(payment_ids))
        
        for payment_id in payment_ids:
            try:
                payment = APPayment.objects.get(pk=payment_id)
                self.approve_payment(payment, approver, notes)
                result.successful.append(payment)
                logger.info(f"Bulk approve: Payment {payment.payment_number} approved successfully")
            except Exception as e:
                result.failed.append({
                    'payment_id': payment_id,
                    'error': str(e)
                })
                logger.error(f"Bulk approve: Payment {payment_id} failed - {str(e)}")
        
        return result

    def bulk_execute_payments(self, payment_ids: List[int], journal_type, notes: str = '') -> BulkOperationResult:
        """Bulk execute multiple payments."""
        result = BulkOperationResult(successful=[], failed=[], total_count=len(payment_ids))
        
        for payment_id in payment_ids:
            try:
                payment = APPayment.objects.get(pk=payment_id)
                self.execute_payment(payment, journal_type)
                result.successful.append(payment)
                logger.info(f"Bulk execute: Payment {payment.payment_number} executed successfully")
            except Exception as e:
                result.failed.append({
                    'payment_id': payment_id,
                    'error': str(e)
                })
                logger.error(f"Bulk execute: Payment {payment_id} failed - {str(e)}")
        
        return result

    def bulk_reconcile_payments(self, payment_ids: List[int], notes: str = '') -> BulkOperationResult:
        """Bulk reconcile multiple payments."""
        result = BulkOperationResult(successful=[], failed=[], total_count=len(payment_ids))
        
        for payment_id in payment_ids:
            try:
                payment = APPayment.objects.get(pk=payment_id)
                self.reconcile_payment(payment, notes)
                result.successful.append(payment)
                logger.info(f"Bulk reconcile: Payment {payment.payment_number} reconciled successfully")
            except Exception as e:
                result.failed.append({
                    'payment_id': payment_id,
                    'error': str(e)
                })
                logger.error(f"Bulk reconcile: Payment {payment_id} failed - {str(e)}")
        
        return result

    def bulk_cancel_payments(self, payment_ids: List[int], reason: str = '') -> BulkOperationResult:
        """Bulk cancel multiple payments."""
        result = BulkOperationResult(successful=[], failed=[], total_count=len(payment_ids))
        
        for payment_id in payment_ids:
            try:
                payment = APPayment.objects.get(pk=payment_id)
                self.cancel_payment(payment, reason)
                result.successful.append(payment)
                logger.info(f"Bulk cancel: Payment {payment.payment_number} cancelled successfully")
            except Exception as e:
                result.failed.append({
                    'payment_id': payment_id,
                    'error': str(e)
                })
                logger.error(f"Bulk cancel: Payment {payment_id} failed - {str(e)}")
        
        return result

    # ------------------------------------------------------------------
    # Utility Methods
    # ------------------------------------------------------------------
    def get_payment_summary(self, organization, status_filter=None, vendor_filter=None):
        """Get payment summary with optional filters."""
        queryset = APPayment.objects.filter(organization=organization)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if vendor_filter:
            queryset = queryset.filter(vendor=vendor_filter)
        
        return queryset.aggregate(
            total_count=('id', 'count'),
            total_amount=('amount', 'sum'),
            avg_amount=('amount', 'avg'),
        )

    def get_payments_by_status(self, organization) -> Dict[str, int]:
        """Get count of payments by status for an organization."""
        return dict(
            APPayment.objects.filter(organization=organization)
            .values('status')
            .annotate(count=models.Count('id'))
            .values_list('status', 'count')
        )

    def validate_payment_for_execution(self, payment: APPayment) -> List[str]:
        """Validate payment before execution and return list of issues."""
        issues = []
        
        if payment.status not in {'approved', 'draft'}:
            issues.append(f"Payment status '{payment.status}' is not suitable for execution")
        
        if not payment.vendor.accounts_payable_account:
            issues.append("Vendor is missing an Accounts Payable account")
        
        if payment.amount <= 0:
            issues.append("Payment amount must be greater than zero")
        
        # Check if there are payment lines
        if not payment.lines.exists():
            issues.append("Payment must have at least one invoice allocation")
        
        # Check currency compatibility
        if hasattr(payment.bank_account, 'currency') and payment.currency:
            if payment.bank_account.currency != payment.currency:
                issues.append("Bank account currency must match payment currency")
        
        # Check for open accounting period
        period = AccountingPeriod.get_current_period(payment.organization)
        if not period:
            issues.append("No open accounting period available for posting")
        
        return issues
