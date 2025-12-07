"""
Service layer for Goods Receipt operations.

Handles:
- GR creation from PO
- GR posting to inventory (stock ledger)
- GL journal entries for procurement posting
- 3-way match validation
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from decimal import Decimal
from typing import Optional, List, Dict, Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from purchasing.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder
from accounting.models import Journal, JournalLine, JournalType, AccountingPeriod
from inventory.models import StockLedger
from purchasing.services.purchase_order_service import PurchaseOrderService


logger = logging.getLogger(__name__)


class GoodsReceiptService:
    """Service layer for Goods Receipt operations."""

    def __init__(self, user):
        self.user = user

    def _get_period_for_date(self, organization, document_date):
        """Return an open accounting period for the given date."""
        period = (
            AccountingPeriod.objects.filter(
                organization=organization,
                start_date__lte=document_date,
                end_date__gte=document_date,
                status="open",
            )
            .order_by("start_date")
            .first()
        )
        if not period:
            period = AccountingPeriod.get_current_period(organization)
        if not period:
            raise ValidationError("No open accounting period is available for posting.")
        return period

    @transaction.atomic
    def create_goods_receipt(
        self,
        purchase_order: PurchaseOrder,
        warehouse,
        lines: List[Dict[str, Any]],
        **kwargs
    ) -> GoodsReceipt:
        """
        Create a draft Goods Receipt from a PO.
        
        Args:
            purchase_order: PurchaseOrder instance
            warehouse: Warehouse instance
            lines: List of dicts with keys: po_line, quantity_received, quantity_accepted
            **kwargs: receipt_date, reference_number, notes
            
        Returns:
            Created GoodsReceipt instance
            
        Raises:
            ValidationError: If validation fails
        """
        gr_number = self._generate_gr_number(purchase_order.organization)
        
        gr = GoodsReceipt.objects.create(
            organization=purchase_order.organization,
            purchase_order=purchase_order,
            number=gr_number,
            receipt_date=kwargs.get("receipt_date") or timezone.now().date(),
            warehouse=warehouse,
            reference_number=kwargs.get("reference_number", ""),
            notes=kwargs.get("notes", ""),
            created_by=self.user,
        )
        
        # Create line items
        for line_data in lines:
            po_line = line_data["po_line"]
            qty_received = line_data["quantity_received"]
            qty_accepted = line_data.get("quantity_accepted", qty_received)
            
            # Validate not over-receiving
            already_received = po_line.quantity_received
            if already_received + qty_received > po_line.quantity_ordered:
                raise ValidationError(
                    f"Cannot receive {qty_received} units for {po_line.product}. "
                    f"Already received {already_received}, ordered {po_line.quantity_ordered}."
                )
            
            GoodsReceiptLine.objects.create(
                receipt=gr,
                po_line=po_line,
                quantity_received=qty_received,
                quantity_accepted=qty_accepted,
                qc_result=line_data.get("qc_result", "pending"),
                notes=line_data.get("notes", ""),
                serial_numbers=line_data.get("serial_numbers", ""),
                batch_number=line_data.get("batch_number", ""),
                expiry_date=line_data.get("expiry_date"),
            )
        
        return gr

    @transaction.atomic
    def post_goods_receipt(self, gr: GoodsReceipt) -> GoodsReceipt:
        """
        Post GR to inventory & GL:
        1. Create stock ledger entries (inventory received)
        2. Create GL journal (Debit Stock, Credit AP Clearing)
        3. Update PO line tracking
        
        Args:
            gr: GoodsReceipt instance
            
        Returns:
            Updated GoodsReceipt instance
            
        Raises:
            ValidationError: If GR already posted or other validation failure
        """
        if gr.status == GoodsReceipt.Status.POSTED:
            raise ValidationError("GR already posted")
        
        if gr.status == GoodsReceipt.Status.CANCELLED:
            raise ValidationError("Cannot post cancelled GR")
        
        # Create stock ledger entries (provisional)
        total_value = Decimal("0")
        posting_datetime = timezone.make_aware(
            datetime.combine(gr.receipt_date, time.min)
        ) if gr.receipt_date else timezone.now()
        for line in gr.lines.select_related("po_line__product"):
            qty_to_post = line.quantity_accepted
            po_line = line.po_line
            
            # Create StockLedger entry
            StockLedger.objects.create(
                organization=gr.organization,
                product=po_line.product,
                warehouse=gr.warehouse,
                txn_type="goods_receipt",
                reference_id=gr.number,
                txn_date=posting_datetime,
                qty_in=qty_to_post,
                qty_out=Decimal("0"),
                unit_cost=po_line.unit_price,
            )
            
            # Update PO line tracking
            po_line.quantity_received += qty_to_post
            po_line.save(update_fields=["quantity_received"])
            
            # Calculate line value for GL posting
            line_value = po_line.unit_price * qty_to_post
            total_value += line_value
        
        # Create GL journal entry (provisional posting)
        # Debit: Inventory account, Credit: AP Clearing account
        journal = self._create_receipt_journal(
            organization=gr.organization,
            gr=gr,
            total_value=total_value,
        )
        
        # Update GR status
        gr.status = GoodsReceipt.Status.POSTED
        gr.journal = journal
        gr.posted_at = timezone.now()
        gr.save()

        # Update PO status based on receipts
        self._update_po_status_after_receipt(gr.purchase_order)
        
        return gr

    @transaction.atomic
    def _create_receipt_journal(self, organization, gr: GoodsReceipt, total_value: Decimal) -> Journal:
        """
        Create GL journal for goods receipt posting.
        Debit: Inventory accounts (by product)
        Credit: AP Clearing account (payables control)
        
        Args:
            organization: Organization instance
            gr: GoodsReceipt instance
            total_value: Total value of goods received
            
        Returns:
            Created Journal instance
        """
        period = self._get_period_for_date(organization, gr.receipt_date)
        # Get or create receipt journal type
        journal_type = self._get_receipt_journal_type(organization)
        
        # Create journal header
        journal = Journal.objects.create(
            organization=organization,
            journal_type=journal_type,
            period=period,
            journal_date=gr.receipt_date,
            reference=gr.number,
            description=f"Goods Receipt {gr.number} from PO {gr.purchase_order.number}",
            currency_code=getattr(gr.purchase_order.currency, "currency_code", organization.base_currency_code or "USD"),
            exchange_rate=getattr(gr.purchase_order, "exchange_rate", Decimal("1")),
            status="draft",
            created_by=self.user,
        )
        
        line_number = 1
        
        # Create debit lines for each line item
        for gr_line in gr.lines.select_related("po_line__product", "po_line__inventory_account"):
            po_line = gr_line.po_line
            line_value = po_line.unit_price * gr_line.quantity_accepted
            
            # Get inventory account (from PO line or product)
            inventory_account = po_line.inventory_account
            if not inventory_account and po_line.product.inventory_account:
                inventory_account = po_line.product.inventory_account
            if not inventory_account:
                raise ValidationError(
                    f"Inventory account missing for product {po_line.product} on PO line {po_line.id}."
                )
            
            if inventory_account:
                JournalLine.objects.create(
                    journal=journal,
                    line_number=line_number,
                    account=inventory_account,
                    debit_amount=line_value,
                    description=f"Received: {po_line.product.name}",
                )
                line_number += 1
        
        # Create credit line to AP Clearing account
        ap_clearing_account = self._get_ap_clearing_account(organization)
        JournalLine.objects.create(
            journal=journal,
            line_number=line_number,
            account=ap_clearing_account,
            credit_amount=total_value,
            description=f"AP provision from GR {gr.number}",
        )
        
        # Post journal (assuming external posting service exists)
        try:
            from accounting.services.posting_service import PostingService
            posting_service = PostingService(self.user)
            posting_service.post(journal)
        except Exception as e:
            logger.warning("Could not post GR journal %s: %s", journal.id, e)
            raise
        
        return journal

    def _get_receipt_journal_type(self, organization) -> JournalType:
        """Get or create the journal type for goods receipts."""
        journal_type, _ = JournalType.objects.get_or_create(
            organization=organization,
            code="GR",
            defaults={
                "name": "Goods Receipt",
                "description": "Goods receipt and inventory posting",
                "is_system_type": True,
            },
        )
        return journal_type

    def _get_ap_clearing_account(self, organization):
        """
        Get the AP Clearing account for provisional posting.
        Falls back to first vendor AP account found.
        """
        from accounting.models import ChartOfAccount
        
        # Try to find a system AP clearing account
        ap_account = (
            ChartOfAccount.objects
            .filter(
                organization=organization,
                account_name__icontains="AP Clearing",
            )
            .first()
        )
        
        if not ap_account:
            # Fall back to any AP account
            ap_account = (
                ChartOfAccount.objects
                .filter(
                    organization=organization,
                    account_name__icontains="Payable",
                )
                .first()
            )
        
        if not ap_account:
            raise ValidationError(
                "No AP account found for organization. Please configure accounting settings."
            )
        
        return ap_account

    def cancel_goods_receipt(self, gr: GoodsReceipt) -> GoodsReceipt:
        """
        Cancel a GR (only allowed in DRAFT status).
        
        Args:
            gr: GoodsReceipt instance
            
        Returns:
            Updated GoodsReceipt instance
            
        Raises:
            ValidationError: If GR already posted
        """
        if gr.status == GoodsReceipt.Status.POSTED:
            raise ValidationError("Cannot cancel posted GR. Reverse posting instead.")
        
        gr.status = GoodsReceipt.Status.CANCELLED
        gr.save(update_fields=["status", "updated_at"])
        
        return gr

    def _update_po_status_after_receipt(self, po: PurchaseOrder) -> PurchaseOrder:
        """Refresh PO status after GR posting based on quantities received."""
        po_service = PurchaseOrderService(self.user)
        return po_service.close_if_fully_received(po)

    def _generate_gr_number(self, organization) -> str:
        """
        Generate a unique GR number for the organization.
        
        Format: GR-YYYY-000001
        """
        from datetime import date
        
        year = date.today().year
        count = GoodsReceipt.objects.filter(
            organization=organization,
            receipt_date__year=year
        ).count() + 1
        
        return f"GR-{year}-{count:06d}"
