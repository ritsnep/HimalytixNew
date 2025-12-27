from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import (
    AccountingPeriod,
    ChartOfAccount,
    Journal,
    JournalLine,
    CurrencyExchangeRate,
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseInvoiceMatch,
    Vendor,
)
from accounting.services.posting_service import PostingService
from accounting.utils.event_utils import emit_integration_event
from accounting.services.inventory_posting_service import InventoryPostingService
from inventory.models import Product, Warehouse


def _enforce_vendor_credit(invoice: PurchaseInvoice, *, user=None):
    """Raise if posting/validating would breach vendor credit limit (credit mode only)."""
    vendor = invoice.vendor
    if not vendor or vendor.credit_limit is None:
        return
    if getattr(invoice, "payment_mode", None) and invoice.payment_mode != "credit":
        return
    # Optionally allow override via metadata flag
    meta = invoice.metadata or {}
    if meta.get("allow_credit_override"):
        return
    if user and user.has_perm("accounting.override_credit_limit"):
        return
    current = vendor.recompute_outstanding_balance()
    projected = current + (invoice.total or Decimal("0"))
    if projected > vendor.credit_limit:
        raise ValidationError(
            f"Credit limit exceeded: outstanding {current:.2f} + invoice {invoice.total:.2f} > limit {vendor.credit_limit:.2f}."
        )


@dataclass
class PurchaseOrderLineSnapshot:
    reference: str
    quantity: Decimal
    unit_cost: Decimal


@dataclass
class ReceiptLineSnapshot:
    reference: str
    quantity_received: Decimal


class PurchaseInvoiceService:
    """
    High-level orchestration for capturing purchase invoices, running three-way
    matches, and posting the payable entry into the general ledger.
    """

    def __init__(self, user):
        self.user = user
        self.posting_service = PostingService(user)

    # ------------------------------------------------------------------
    # Invoice lifecycle helpers
    # ------------------------------------------------------------------
    def _calculate_due_date(self, vendor: Vendor, payment_term, invoice_date):
        if payment_term:
            return payment_term.calculate_due_date(invoice_date)
        if vendor.payment_term:
            return vendor.payment_term.calculate_due_date(invoice_date)
        return invoice_date

    def _resolve_exchange_rate(self, organization, currency, document_date) -> Decimal:
        if not currency or currency.currency_code == getattr(organization, "base_currency_code", None):
            return Decimal("1")
        rate_value = (
            CurrencyExchangeRate.objects.filter(
                organization=organization,
                from_currency=currency,
                to_currency__currency_code=getattr(organization, "base_currency_code", None),
                rate_date__lte=document_date,
                is_active=True,
            )
            .order_by("-rate_date")
            .values_list("exchange_rate", flat=True)
            .first()
        )
        try:
            return Decimal(str(rate_value)) if rate_value is not None else Decimal("1")
        except Exception:  # noqa: BLE001
            return Decimal("1")

    @transaction.atomic
    def create_invoice(
        self,
        *,
        organization,
        vendor: Vendor,
        invoice_number: Optional[str] = None,
        invoice_date,
        currency,
        exchange_rate: Optional[Decimal] = None,
        lines: Iterable[dict],
        payment_term=None,
        due_date=None,
        payment_mode: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> PurchaseInvoice:
        if vendor.accounts_payable_account_id is None:
            raise ValidationError("Vendor is missing a default Accounts Payable account.")

        payment_term = payment_term or getattr(vendor, "payment_term", None)
        due_date = due_date or self._calculate_due_date(vendor, payment_term, invoice_date)
        metadata = metadata or {}
        exchange_rate = exchange_rate or self._resolve_exchange_rate(organization, currency, invoice_date)
        payment_mode = payment_mode or 'credit'

        invoice = PurchaseInvoice.objects.create(
            organization=organization,
            vendor=vendor,
            vendor_display_name=vendor.display_name,
            invoice_number=invoice_number or '',
            invoice_date=invoice_date,
            due_date=due_date,
            payment_term=payment_term,
            payment_mode=payment_mode,
            currency=currency,
            exchange_rate=exchange_rate,
            status='draft',
            created_by=self.user,
            updated_by=self.user,
            metadata=metadata,
        )

        for index, line in enumerate(lines, start=1):
            PurchaseInvoiceLine.objects.create(
                invoice=invoice,
                line_number=index,
                description=line.get('description', ''),
                product_code=line.get('product_code', ''),
                quantity=line.get('quantity', Decimal('1')),
                unit_cost=line.get('unit_cost', Decimal('0')),
                discount_amount=line.get('discount_amount', Decimal('0')),
                account=line['account'],
                tax_code=line.get('tax_code'),
                tax_amount=line.get('tax_amount', Decimal('0')),
                cost_center=line.get('cost_center'),
                department=line.get('department'),
                project=line.get('project'),
                dimension_value=line.get('dimension_value'),
                po_reference=line.get('po_reference', ''),
                receipt_reference=line.get('receipt_reference', ''),
                metadata=line.get('metadata', {}),
            )

        invoice.recompute_totals(save=True)
        return invoice

    @transaction.atomic
    def validate_invoice(self, invoice: PurchaseInvoice) -> PurchaseInvoice:
        if invoice.lines.count() == 0:
            raise ValidationError("Purchase invoice must contain at least one line.")
        invoice.recompute_totals(save=True)
        if invoice.total <= 0:
            raise ValidationError("Purchase invoice total must be greater than zero.")
        if invoice.vendor and invoice.vendor.default_currency and invoice.currency != invoice.vendor.default_currency:
            if not self.user.has_perm("accounting.override_currency_mismatch"):
                raise ValidationError("Invoice currency must match vendor default currency or require override permission.")
        _enforce_vendor_credit(invoice, user=self.user)
        invoice.status = 'validated'
        invoice.updated_by = self.user
        invoice.save(update_fields=['status', 'updated_by', 'updated_at', 'subtotal', 'tax_total', 'total', 'base_currency_total'])
        return invoice

    # ------------------------------------------------------------------
    # Three-way matching
    # ------------------------------------------------------------------
    @transaction.atomic
    def perform_three_way_match(
        self,
        invoice: PurchaseInvoice,
        purchase_order_lines: Optional[Iterable[PurchaseOrderLineSnapshot | dict]] = None,
        receipt_lines: Optional[Iterable[ReceiptLineSnapshot | dict]] = None,
    ) -> PurchaseInvoice:
        """
        Allow multiple invoice lines to reference the same PO line by tracking remaining quantities.
        """
        purchase_order_lines = purchase_order_lines or []
        receipt_lines = receipt_lines or []

        # Build PO and receipt lookup maps by reference and PK (if provided)
        po_by_ref = {}
        po_by_id = {}
        for line in purchase_order_lines:
            ref = getattr(line, "reference", None) or getattr(line, "po_reference", None) or getattr(line, "pk", None) or getattr(line, "id", None)
            if ref is not None:
                po_by_ref[str(ref)] = line
            try:
                pk_val = getattr(line, "pk", None) or getattr(line, "id", None)
                if pk_val is not None:
                    po_by_id[int(pk_val)] = line
            except Exception:
                pass

        receipt_by_ref = {
            str(getattr(line, "reference", None) or getattr(line, "receipt_reference", None) or getattr(line, "pk", None) or getattr(line, "id", None)): line
            for line in receipt_lines
        }

        # Track remaining expected qty per PO line so multiple invoice lines can share
        remaining_expected = {}
        for ref, line in po_by_ref.items():
            try:
                qty = getattr(line, "quantity", None) or getattr(line, "quantity_ordered", None) or getattr(line, "ordered_quantity", None) or 0
                remaining_expected[ref] = Decimal(str(qty))
            except Exception:
                remaining_expected[ref] = Decimal("0")

        invoice.match_results.all().delete()

        all_matched = True
        summary = []

        for line in invoice.lines.all():
            # Resolve the PO line reference; prefer numeric id if present in po_reference
            po_ref_raw = line.po_reference or ""
            po_line_obj = None
            reference_key = po_ref_raw or line.product_code or f"LINE-{line.line_number}"
            try:
                ref_id = int(po_ref_raw)
                po_line_obj = po_by_id.get(ref_id)
            except Exception:
                po_line_obj = None
            if po_line_obj is None:
                po_line_obj = po_by_ref.get(str(reference_key))

            receipt_snapshot = receipt_by_ref.get(str(line.receipt_reference or reference_key))

            expected_qty = Decimal("0")
            unit_cost_expected = line.unit_cost
            if po_line_obj:
                try:
                    expected_qty = remaining_expected.get(str(reference_key), Decimal("0"))
                except Exception:
                    expected_qty = Decimal("0")
                try:
                    unit_cost_expected = Decimal(
                        str(
                            getattr(po_line_obj, "unit_cost", None)
                            or getattr(po_line_obj, "unit_price", None)
                            or line.unit_cost
                        )
                    )
                except Exception:
                    unit_cost_expected = line.unit_cost

            received_qty = Decimal("0")
            if receipt_snapshot:
                try:
                    received_qty = Decimal(
                        str(
                            getattr(receipt_snapshot, "quantity_received", None)
                            or getattr(receipt_snapshot, "qty_received", None)
                            or getattr(receipt_snapshot, "quantity", None)
                            or 0
                        )
                    )
                except Exception:
                    received_qty = Decimal("0")

            invoiced_qty = line.quantity
            unit_variance = (line.unit_cost - unit_cost_expected).quantize(Decimal("0.0001"))

            # Determine status considering remaining expected quantity
            status = "matched"
            if po_line_obj:
                if expected_qty <= 0 and invoiced_qty > 0:
                    status = "over_receipt"
                elif invoiced_qty < expected_qty:
                    status = "short_receipt"
                elif invoiced_qty > expected_qty:
                    status = "over_receipt"
                elif unit_variance != Decimal("0.0000"):
                    status = "price_variance"
            else:
                # No PO reference; fall back to receipt comparison if present
                if invoiced_qty > received_qty:
                    status = "over_receipt"
                elif invoiced_qty < received_qty:
                    status = "short_receipt"
                elif unit_variance != Decimal("0.0000"):
                    status = "price_variance"

            if status != "matched":
                all_matched = False

            PurchaseInvoiceMatch.objects.create(
                invoice=invoice,
                invoice_line=line,
                po_reference=str(reference_key),
                receipt_reference=line.receipt_reference or str(reference_key),
                expected_quantity=expected_qty,
                received_quantity=received_qty,
                invoiced_quantity=invoiced_qty,
                unit_price_variance=unit_variance,
                status=status,
            )
            summary.append(
                {
                    "reference": str(reference_key),
                    "status": status,
                    "expected_quantity": str(expected_qty),
                    "received_quantity": str(received_qty),
                    "invoiced_quantity": str(invoiced_qty),
                    "unit_variance": str(unit_variance),
                }
            )

            # Reduce remaining expected qty for this PO line so subsequent lines see the residual
            if po_line_obj:
                try:
                    remaining_expected[str(reference_key)] = max(
                        Decimal("0"),
                        remaining_expected.get(str(reference_key), Decimal("0")) - invoiced_qty,
                    )
                except Exception:
                    pass

        invoice.match_status = 'matched' if all_matched else 'variance'
        if all_matched and invoice.status in {'validated', 'draft'}:
            invoice.status = 'matched'
        invoice.match_summary = summary
        invoice.updated_by = self.user
        invoice.save(update_fields=['status', 'match_status', 'match_summary', 'updated_by', 'updated_at'])
        return invoice

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------
    @transaction.atomic
    def post_invoice(
        self,
        invoice: PurchaseInvoice,
        journal_type,
        *,
        use_grir: bool = False,
        warehouse: Optional[Warehouse] = None,
        grir_account: Optional[ChartOfAccount] = None,
        idempotency_key: Optional[str] = None,
    ) -> Journal:
        invoice = PurchaseInvoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status == "posted" and invoice.journal_id:
            return invoice.journal
        if idempotency_key:
            metadata = dict(invoice.metadata or {})
            existing_key = metadata.get("idempotency_key")
            if existing_key and existing_key != idempotency_key:
                raise ValidationError("Idempotency key mismatch for this invoice.")
            metadata["idempotency_key"] = idempotency_key
            invoice.metadata = metadata
            invoice.save(update_fields=["metadata"])
        if invoice.status not in {'validated', 'matched', 'ready_for_posting'}:
            raise ValidationError("Invoice must be validated before posting.")
        if invoice.vendor.accounts_payable_account is None:
            raise ValidationError("Vendor is missing an Accounts Payable account.")
        if use_grir and not grir_account:
            raise ValidationError("GR/IR account must be provided when use_grir is True.")
        if use_grir and not warehouse:
            raise ValidationError("Warehouse is required for inventory receipts when use_grir is True.")

        invoice.recompute_totals(save=True)
        _enforce_vendor_credit(invoice, user=self.user)
        organization = invoice.organization
        period = AccountingPeriod.get_current_period(organization)
        if not period:
            raise ValidationError("No open accounting period is available for posting.")

        inventory_service = InventoryPostingService(organization=organization)

        journal = Journal.objects.create(
            organization=organization,
            journal_type=journal_type,
            period=period,
            journal_date=invoice.invoice_date,
            description=f"Purchase invoice {invoice.invoice_number} for {invoice.vendor_display_name}",
            currency_code=invoice.currency.currency_code,
            exchange_rate=invoice.exchange_rate,
            status='draft',
            created_by=self.user,
            updated_by=self.user,
        )

        line_number = 1
        for pil in invoice.lines.select_related('account', 'tax_code'):
            product = None
            if pil.product_code:
                product = Product.objects.filter(organization=organization, code=pil.product_code).first()

            if use_grir and product and product.is_inventory_item:
                receipt = inventory_service.record_receipt(
                    product=product,
                    warehouse=warehouse,
                    quantity=pil.quantity,
                    unit_cost=pil.unit_cost,
                    grir_account=grir_account,
                    reference_id=invoice.invoice_number,
                )
                # Dr Inventory
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=receipt.debit_account,
                    description=f"Inventory receipt for {product.code}",
                    debit_amount=receipt.total_cost,
                    department=pil.department,
                    project=pil.project,
                    cost_center=pil.cost_center,
                    created_by=self.user,
                )
                line_number += 1
                # Cr GR/IR (receipt)
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=receipt.credit_account,
                    description=f"GR/IR for {product.code}",
                    credit_amount=receipt.total_cost,
                    created_by=self.user,
                )
                line_number += 1
                # Dr GR/IR to clear, Cr AP later
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=receipt.credit_account,
                    description=f"Clear GR/IR for {product.code}",
                    debit_amount=receipt.total_cost,
                    created_by=self.user,
                )
                line_number += 1
                # Skip expense debit; inventory handled
            else:
                debit_amount = pil.line_total
                if debit_amount > 0:
                    JournalLine.objects.create(
                        journal=journal,
                        line_number=line_number,
                        account=pil.account,
                        description=pil.description,
                        debit_amount=debit_amount,
                        department=pil.department,
                        project=pil.project,
                        cost_center=pil.cost_center,
                        created_by=self.user,
                    )
                    line_number += 1

            if pil.tax_amount > 0 and pil.tax_code and pil.tax_code.purchase_account:
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=pil.tax_code.purchase_account,
                    description=f"Input tax for {invoice.invoice_number}",
                    debit_amount=pil.tax_amount,
                    created_by=self.user,
                )
                line_number += 1

        JournalLine.objects.create(
            journal=journal,
            line_number=line_number,
            account=invoice.vendor.accounts_payable_account,
            description=f"Accounts payable for {invoice.vendor_display_name}",
            credit_amount=invoice.total,
            created_by=self.user,
        )

        posted_journal = self.posting_service.post(journal)
        invoice.status = 'posted'
        invoice.journal = posted_journal
        invoice.updated_by = self.user
        invoice.save(update_fields=['status', 'journal', 'updated_by', 'updated_at'])
        emit_integration_event(
            'purchase_invoice_posted',
            invoice,
            {
                'invoice_number': invoice.invoice_number,
                'vendor': invoice.vendor_display_name,
                'total': str(invoice.total),
            },
        )
        return posted_journal

    @staticmethod
    def calculate_totals(organization, line_items, header_discount=None):
        """
        Calculate totals for purchase invoice line items.

        Args:
            organization: Organization instance
            line_items: List of line item dictionaries
            header_discount: Header discount information

        Returns:
            Dictionary with calculated totals
        """
        from decimal import Decimal

        subtotal = Decimal('0.00')
        total_vat = Decimal('0.00')
        total_discount = Decimal('0.00')

        for item in line_items:
            quantity = Decimal(str(item.get('quantity', 0)))
            rate = Decimal(str(item.get('rate', 0)))
            discount = Decimal(str(item.get('discount', 0)))
            vat_rate = Decimal(str(item.get('vat_rate', 0)))

            line_total = quantity * rate
            line_discount = (line_total * discount / 100) if discount else Decimal('0.00')
            line_vat = (line_total - line_discount) * vat_rate / 100

            subtotal += line_total
            total_discount += line_discount
            total_vat += line_vat

        # Apply header discount if provided
        header_discount_amount = Decimal('0.00')
        if header_discount:
            discount_value = Decimal(str(header_discount.get('value', 0)))
            discount_type = header_discount.get('type', 'amount')

            if discount_type == 'percentage':
                header_discount_amount = subtotal * discount_value / 100
            else:
                header_discount_amount = discount_value

        grand_total = subtotal - total_discount - header_discount_amount + total_vat

        return {
            'subtotal': subtotal,
            'total_discount': total_discount + header_discount_amount,
            'total_vat': total_vat,
            'grand_total': grand_total,
        }

    @staticmethod
    def get_order_lines_for_invoice(organization, order_id):
        """
        Get purchase order lines for applying to invoice.

        Args:
            organization: Organization instance
            order_id: Purchase order ID

        Returns:
            List of order line dictionaries
        """
        # This would typically query purchase orders
        # For now, return empty list as placeholder
        return []

    @staticmethod
    def amount_to_words(amount):
        """
        Convert amount to words.

        Args:
            amount: Decimal amount

        Returns:
            String representation in words
        """
        # Simple implementation - could be enhanced
        try:
            from num2words import num2words
            return num2words(amount, to='currency', currency='NPR').title()
        except ImportError:
            # Fallback if num2words not available
            return f"NPR {amount:,.2f}"
