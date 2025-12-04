"""
Service layer for Purchase Order operations.

Handles:
- PO creation with line items
- Status transitions (Draft -> Approved -> Sent -> Received -> Closed)
- Totals calculation
- Number generation
"""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from purchasing.models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderService:
    """Service layer for Purchase Order operations."""

    def __init__(self, user):
        self.user = user

    @transaction.atomic
    def create_purchase_order(
        self,
        organization,
        vendor,
        lines: List[Dict[str, Any]],
        **kwargs
    ) -> PurchaseOrder:
        """
        Create a draft PO with line items.
        
        Args:
            organization: Organization instance
            vendor: Vendor instance
            lines: List of dicts with keys: product, quantity_ordered, unit_price, vat_rate
            **kwargs: order_date, due_date, currency, notes, expected_receipt_date
        
        Returns:
            Created PurchaseOrder instance
            
        Raises:
            ValidationError: If validation fails
        """
        po_number = self._generate_po_number(organization)
        
        po = PurchaseOrder.objects.create(
            organization=organization,
            vendor=vendor,
            number=po_number,
            order_date=kwargs.get("order_date") or timezone.now().date(),
            due_date=kwargs.get("due_date"),
            currency=kwargs.get("currency"),
            expected_receipt_date=kwargs.get("expected_receipt_date"),
            notes=kwargs.get("notes", ""),
            created_by=self.user,
        )
        
        # Create line items
        for line_data in lines:
            PurchaseOrderLine.objects.create(
                purchase_order=po,
                product=line_data["product"],
                quantity_ordered=line_data["quantity_ordered"],
                unit_price=line_data["unit_price"],
                vat_rate=line_data.get("vat_rate", Decimal("0")),
                expected_delivery_date=line_data.get("expected_delivery_date"),
                inventory_account=line_data.get("inventory_account"),
                expense_account=line_data.get("expense_account"),
            )
        
        # Calculate totals
        po.recalc_totals()
        po.save(skip_recalc=True)
        
        return po

    def approve_purchase_order(self, po: PurchaseOrder) -> PurchaseOrder:
        """
        Move PO from DRAFT to APPROVED.
        
        Args:
            po: PurchaseOrder instance
            
        Returns:
            Updated PurchaseOrder instance
            
        Raises:
            ValidationError: If PO not in DRAFT status
        """
        if po.status != PurchaseOrder.Status.DRAFT:
            raise ValidationError(
                f"Cannot approve PO in {po.status} status. Must be DRAFT."
            )
        
        po.status = PurchaseOrder.Status.APPROVED
        po.save(update_fields=["status", "updated_at"])
        
        return po

    def mark_sent(self, po: PurchaseOrder) -> PurchaseOrder:
        """
        Mark PO as sent to vendor.
        
        Args:
            po: PurchaseOrder instance
            
        Returns:
            Updated PurchaseOrder instance
            
        Raises:
            ValidationError: If PO not in APPROVED status
        """
        if po.status != PurchaseOrder.Status.APPROVED:
            raise ValidationError(
                f"Cannot send PO in {po.status} status. Must be APPROVED."
            )
        
        po.status = PurchaseOrder.Status.SENT
        po.send_date = timezone.now().date()
        po.save(update_fields=["status", "send_date", "updated_at"])
        
        return po

    def cancel_purchase_order(self, po: PurchaseOrder) -> PurchaseOrder:
        """
        Cancel a PO (only allowed in DRAFT status).
        
        Args:
            po: PurchaseOrder instance
            
        Returns:
            Updated PurchaseOrder instance
            
        Raises:
            ValidationError: If PO has received items or invoices
        """
        # Check if any items have been received
        for line in po.lines.all():
            if line.quantity_received > 0:
                raise ValidationError(
                    f"Cannot cancel PO with received items. Line {line.id} has {line.quantity_received} received."
                )
            if line.quantity_invoiced > 0:
                raise ValidationError(
                    f"Cannot cancel PO with invoiced items. Line {line.id} has {line.quantity_invoiced} invoiced."
                )
        
        po.status = PurchaseOrder.Status.CLOSED
        po.save(update_fields=["status", "updated_at"])
        
        return po

    def _generate_po_number(self, organization) -> str:
        """
        Generate a unique PO number for the organization.
        
        Format: PO-YYYY-000001
        """
        from datetime import date
        
        year = date.today().year
        count = PurchaseOrder.objects.filter(
            organization=organization,
            order_date__year=year
        ).count() + 1
        
        return f"PO-{year}-{count:06d}"

    def update_po_line(
        self,
        po_line: PurchaseOrderLine,
        **kwargs
    ) -> PurchaseOrderLine:
        """
        Update a PO line item.
        
        Args:
            po_line: PurchaseOrderLine instance
            **kwargs: Fields to update
            
        Returns:
            Updated PurchaseOrderLine instance
        """
        for key, value in kwargs.items():
            if hasattr(po_line, key):
                setattr(po_line, key, value)
        
        po_line.save()
        
        # Recalculate PO totals
        po_line.purchase_order.recalc_totals()
        po_line.purchase_order.save(skip_recalc=True)
        
        return po_line

    def delete_po_line(self, po_line: PurchaseOrderLine) -> PurchaseOrder:
        """
        Delete a PO line and recalculate totals.
        
        Args:
            po_line: PurchaseOrderLine instance
            
        Returns:
            Updated PurchaseOrder instance
        """
        po = po_line.purchase_order
        po_line.delete()
        
        # Recalculate totals
        po.recalc_totals()
        po.save(skip_recalc=True)
        
        return po
