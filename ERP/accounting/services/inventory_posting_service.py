from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from inventory.models import InventoryItem, Product, StockLedger, Warehouse
from accounting.models import ChartOfAccount, JournalLine


@dataclass
class InventoryPostingResult:
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    inventory_item: InventoryItem
    ledger_entry: StockLedger
    debit_account: ChartOfAccount
    credit_account: ChartOfAccount


class InventoryPostingService:
    """
    Handle inventory movement accounting with weighted-average costing.

    This service does not post journals itself; it returns the affected GL
    accounts so callers can create balanced JournalLines in their own
    transaction.
    """

    def __init__(self, *, organization):
        self.organization = organization

    def _get_or_create_item(self, product: Product, warehouse: Warehouse) -> InventoryItem:
        item, _ = InventoryItem.objects.get_or_create(
            organization=self.organization,
            product=product,
            warehouse=warehouse,
            defaults={"quantity_on_hand": Decimal("0"), "unit_cost": Decimal("0")},
        )
        return item

    @transaction.atomic
    def record_receipt(
        self,
        *,
        product: Product,
        warehouse: Warehouse,
        quantity: Decimal,
        unit_cost: Decimal,
        grir_account: ChartOfAccount,
        reference_id: str,
        location=None,
        batch=None,
        txn_date=None,
    ) -> InventoryPostingResult:
        """
        Receipt: Dr Inventory, Cr GR/IR. Updates weighted-average cost.
        """
        if not product.inventory_account:
            raise ValueError("Product is missing an inventory account.")

        txn_date = txn_date or timezone.now()
        item = self._get_or_create_item(product, warehouse)

        current_qty = item.quantity_on_hand
        current_cost = item.unit_cost
        new_qty = current_qty + quantity

        if new_qty <= 0:
            raise ValueError("Receipt would drive on-hand to zero or negative; aborting.")

        total_existing_value = current_qty * current_cost
        total_new_value = quantity * unit_cost
        new_unit_cost = (total_existing_value + total_new_value) / new_qty

        item.quantity_on_hand = new_qty
        item.unit_cost = new_unit_cost
        item.save(update_fields=["quantity_on_hand", "unit_cost", "updated_at"])

        ledger = StockLedger.objects.create(
            organization=self.organization,
            product=product,
            warehouse=warehouse,
            location=location,
            batch=batch,
            txn_type="receipt",
            reference_id=reference_id,
            txn_date=txn_date,
            qty_in=quantity,
            unit_cost=new_unit_cost,
        )

        return InventoryPostingResult(
            quantity=quantity,
            unit_cost=new_unit_cost,
            total_cost=quantity * new_unit_cost,
            inventory_item=item,
            ledger_entry=ledger,
            debit_account=product.inventory_account,
            credit_account=grir_account,
        )

    @transaction.atomic
    def record_issue(
        self,
        *,
        product: Product,
        warehouse: Warehouse,
        quantity: Decimal,
        reference_id: str,
        cogs_account: Optional[ChartOfAccount] = None,
        location=None,
        batch=None,
        txn_date=None,
    ) -> InventoryPostingResult:
        """
        Issue: Dr COGS, Cr Inventory at weighted-average cost.
        """
        if not product.inventory_account or not product.expense_account:
            raise ValueError("Product is missing inventory or expense (COGS) account.")

        txn_date = txn_date or timezone.now()
        item = self._get_or_create_item(product, warehouse)

        if item.quantity_on_hand < quantity:
            raise ValueError("Insufficient quantity on hand for issue.")

        item.quantity_on_hand -= quantity
        item.save(update_fields=["quantity_on_hand", "updated_at"])

        ledger = StockLedger.objects.create(
            organization=self.organization,
            product=product,
            warehouse=warehouse,
            location=location,
            batch=batch,
            txn_type="issue",
            reference_id=reference_id,
            txn_date=txn_date,
            qty_out=quantity,
            unit_cost=item.unit_cost,
        )

        total_cost = (item.unit_cost or Decimal("0")) * quantity
        return InventoryPostingResult(
            quantity=quantity,
            unit_cost=item.unit_cost,
            total_cost=total_cost,
            inventory_item=item,
            ledger_entry=ledger,
            debit_account=cogs_account or product.expense_account,
            credit_account=product.inventory_account,
        )

