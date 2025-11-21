from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from accounting.models import (
    AccountingPeriod,
    ARReceipt,
    ARReceiptLine,
    Journal,
    JournalLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from accounting.ird_service import submit_invoice_to_ird
from accounting.services.posting_service import PostingService
from accounting.services.inventory_posting_service import InventoryPostingService
from accounting.utils.event_utils import emit_integration_event
from Inventory.models import Product, Warehouse


@dataclass
class ReceiptAllocation:
    amount: Decimal
    discount: Decimal = Decimal('0')


class SalesInvoiceService:
    """Handle sales invoice creation, validation, posting, and receipt allocation."""

    def __init__(self, user):
        self.user = user
        self.posting_service = PostingService(user)
        self.logger = logging.getLogger(__name__)

    def _calculate_due_date(self, customer, payment_term, invoice_date):
        payment_term = payment_term or getattr(customer, 'payment_term', None)
        if payment_term and invoice_date:
            return payment_term.calculate_due_date(invoice_date)
        return invoice_date

    @transaction.atomic
    def create_invoice(
        self,
        *,
        organization,
        customer,
        invoice_number: Optional[str] = None,
        invoice_date,
        currency,
        lines: Iterable[dict],
        payment_term=None,
        due_date=None,
        exchange_rate: Decimal = Decimal('1'),
        metadata: Optional[dict] = None,
    ) -> SalesInvoice:
        if customer.accounts_receivable_account_id is None:
            raise ValidationError("Customer is missing an Accounts Receivable account.")

        payment_term = payment_term or getattr(customer, 'payment_term', None)
        metadata = metadata or {}

        invoice = SalesInvoice.objects.create(
            organization=organization,
            customer=customer,
            customer_display_name=customer.display_name,
            invoice_number=invoice_number or '',
            invoice_date=invoice_date,
            due_date=due_date or self._calculate_due_date(customer, payment_term, invoice_date),
            payment_term=payment_term,
            currency=currency,
            exchange_rate=exchange_rate,
            status='draft',
            created_by=self.user,
            updated_by=self.user,
            metadata=metadata,
        )

        for index, line_data in enumerate(lines, start=1):
            SalesInvoiceLine.objects.create(
                invoice=invoice,
                line_number=index,
                description=line_data.get('description', ''),
                product_code=line_data.get('product_code', ''),
                quantity=line_data.get('quantity', Decimal('1')),
                unit_price=line_data.get('unit_price', Decimal('0')),
                discount_amount=line_data.get('discount_amount', Decimal('0')),
                revenue_account=line_data['revenue_account'],
                tax_code=line_data.get('tax_code'),
                tax_amount=line_data.get('tax_amount', Decimal('0')),
                cost_center=line_data.get('cost_center'),
                department=line_data.get('department'),
                project=line_data.get('project'),
                dimension_value=line_data.get('dimension_value'),
                metadata=line_data.get('metadata', {}),
            )

        invoice.recompute_totals(save=True)
        return invoice

    @transaction.atomic
    def validate_invoice(self, invoice: SalesInvoice) -> SalesInvoice:
        if invoice.lines.count() == 0:
            raise ValidationError("Sales invoice must contain at least one line.")
        invoice.recompute_totals(save=True)
        if invoice.total <= 0:
            raise ValidationError("Sales invoice total must be greater than zero.")
        invoice.status = 'validated'
        invoice.updated_by = self.user
        invoice.save(update_fields=['status', 'updated_by', 'updated_at', 'subtotal', 'tax_total', 'total', 'base_currency_total'])
        return invoice

    @transaction.atomic
    def _should_submit_to_ird(self, submit_to_ird: Optional[bool]) -> bool:
        """Determine whether to submit the invoice to IRD based on override or settings."""
        if submit_to_ird is not None:
            return submit_to_ird
        return getattr(settings, "IRD_ENABLE_AUTO_SUBMIT", False)

    def _submit_to_ird(self, invoice: SalesInvoice) -> None:
        """Best-effort IRD submission; failures are logged but do not block posting."""
        try:
            result = submit_invoice_to_ird(invoice)
            emit_integration_event(
                "sales_invoice_submitted_to_ird",
                invoice,
                {
                    "invoice_number": invoice.invoice_number,
                    "ack_id": result.ack_id,
                    "signature": result.signature,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "IRD submission failed for invoice %s: %s",
                invoice.invoice_number,
                exc,
                exc_info=True,
            )

    def post_invoice(
        self,
        invoice: SalesInvoice,
        journal_type,
        *,
        submit_to_ird: Optional[bool] = None,
        warehouse: Optional[Warehouse] = None,
    ) -> Journal:
        if invoice.status not in {'validated', 'draft'}:
            raise ValidationError("Invoice must be validated before posting.")
        if invoice.customer.accounts_receivable_account is None:
            raise ValidationError("Customer is missing an Accounts Receivable account.")

        organization = invoice.organization
        inventory_service = InventoryPostingService(organization=organization)
        if warehouse and warehouse.organization_id != organization.id:
            raise ValidationError("Warehouse must belong to the same organization as the invoice.")

        period = AccountingPeriod.get_current_period(organization)
        if not period:
            raise ValidationError("No open accounting period is available for posting.")

        invoice.recompute_totals(save=True)

        journal = Journal.objects.create(
            organization=organization,
            journal_type=journal_type,
            period=period,
            journal_date=invoice.invoice_date,
            description=f"Sales invoice {invoice.invoice_number} for {invoice.customer_display_name}",
            currency_code=invoice.currency.currency_code,
            exchange_rate=invoice.exchange_rate,
            status='draft',
            created_by=self.user,
            updated_by=self.user,
        )

        line_number = 1
        for sil in invoice.lines.select_related('revenue_account', 'tax_code'):
            JournalLine.objects.create(
                journal=journal,
                line_number=line_number,
                account=sil.revenue_account,
                description=sil.description,
                credit_amount=sil.line_total,
                department=sil.department,
                project=sil.project,
                cost_center=sil.cost_center,
                created_by=self.user,
            )
            line_number += 1
            if sil.tax_amount > 0 and sil.tax_code and sil.tax_code.sales_account:
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=sil.tax_code.sales_account,
                    description=f"Output tax for {invoice.invoice_number}",
                    credit_amount=sil.tax_amount,
                    created_by=self.user,
                )
                line_number += 1

            # COGS and Inventory for inventory items
            product = None
            if sil.product_code:
                product = Product.objects.filter(organization=organization, code=sil.product_code).first()
            if product and product.is_inventory_item:
                if warehouse is None:
                    raise ValidationError("Warehouse is required when posting inventory items.")
                try:
                    issue = inventory_service.record_issue(
                        product=product,
                        warehouse=warehouse,
                        quantity=sil.quantity,
                        reference_id=invoice.invoice_number or str(invoice.pk),
                        cogs_account=product.expense_account,
                    )
                except ValueError as exc:  # noqa: BLE001
                    raise ValidationError(str(exc)) from exc

                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=issue.debit_account,
                    description=f"COGS for {product.code}",
                    debit_amount=issue.total_cost,
                    department=sil.department,
                    project=sil.project,
                    cost_center=sil.cost_center,
                    created_by=self.user,
                )
                line_number += 1
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=issue.credit_account,
                    description=f"Inventory out for {product.code}",
                    credit_amount=issue.total_cost,
                    department=sil.department,
                    project=sil.project,
                    cost_center=sil.cost_center,
                    created_by=self.user,
                )
                line_number += 1

        JournalLine.objects.create(
            journal=journal,
            line_number=line_number,
            account=invoice.customer.accounts_receivable_account,
            description=f"Accounts receivable for {invoice.customer_display_name}",
            debit_amount=invoice.total,
            created_by=self.user,
        )

        posted_journal = self.posting_service.post(journal)
        invoice.status = 'posted'
        invoice.journal = posted_journal
        invoice.updated_by = self.user
        invoice.save(update_fields=['status', 'journal', 'updated_by', 'updated_at'])

        if self._should_submit_to_ird(submit_to_ird):
            self._submit_to_ird(invoice)

        emit_integration_event(
            'sales_invoice_posted',
            invoice,
            {
                'invoice_number': invoice.invoice_number,
                'customer': invoice.customer_display_name,
                'total': str(invoice.total),
            },
        )
        return posted_journal

    @transaction.atomic
    def apply_receipt(
        self,
        *,
        organization,
        customer,
        receipt_number: str,
        receipt_date,
        currency,
        exchange_rate: Decimal,
        amount: Decimal,
        allocations: dict[SalesInvoice, ReceiptAllocation],
        payment_method: str = 'bank_transfer',
        reference: str = '',
    ) -> ARReceipt:
        receipt = ARReceipt.objects.create(
            organization=organization,
            customer=customer,
            receipt_number=receipt_number,
            receipt_date=receipt_date,
            payment_method=payment_method,
            reference=reference,
            currency=currency,
            exchange_rate=exchange_rate,
            amount=amount,
            created_by=self.user,
            updated_by=self.user,
        )

        total_applied = Decimal('0')
        for invoice, alloc in allocations.items():
            if invoice.customer_id != customer.pk:
                raise ValidationError("Receipt allocations must belong to the same customer.")
            if invoice.status != 'posted':
                raise ValidationError("Receipt can only be applied to posted invoices.")
            ARReceiptLine.objects.create(
                receipt=receipt,
                invoice=invoice,
                applied_amount=alloc.amount,
                discount_taken=alloc.discount,
            )
            total_applied += alloc.amount + alloc.discount

        if total_applied > amount:
            raise ValidationError("Applied amount cannot exceed receipt amount.")

        emit_integration_event(
            'ar_receipt_recorded',
            receipt,
            {
                'receipt_number': receipt.receipt_number,
                'customer': receipt.customer.display_name,
                'amount': str(receipt.amount),
            },
        )
        return receipt
