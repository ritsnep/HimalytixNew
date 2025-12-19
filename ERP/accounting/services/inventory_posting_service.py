from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from inventory.models import (
    CostLayer,
    CostingMethod,
    InventoryItem,
    Product,
    StockLedger,
    Warehouse,
)
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


class CostCalculator:
    def __init__(self, *, organization, product, warehouse, location=None, batch=None):
        self.organization = organization
        self.product = product
        self.warehouse = warehouse
        self.location = location
        self.batch = batch

    def _layer_queryset(self):
        qs = CostLayer.objects.filter(
            organization=self.organization,
            product=self.product,
            warehouse=self.warehouse,
            quantity_available__gt=Decimal("0"),
        )
        if self.location is not None:
            qs = qs.filter(location=self.location)
        else:
            qs = qs.filter(location__isnull=True)
        if self.batch is not None:
            qs = qs.filter(batch=self.batch)
        else:
            qs = qs.filter(batch__isnull=True)
        return qs

    def create_layer(self, quantity, unit_cost, reference_id):
        return CostLayer.objects.create(
            organization=self.organization,
            product=self.product,
            warehouse=self.warehouse,
            location=self.location,
            batch=self.batch,
            reference_id=reference_id or "",
            quantity_received=quantity,
            quantity_available=quantity,
            unit_cost=unit_cost,
        )

    def consume_layers(self, quantity, method):
        order = "created_at" if method == CostingMethod.FIFO else "-created_at"
        layers = self._layer_queryset().order_by(order)
        remaining = quantity
        total_cost = Decimal("0")
        for layer in layers:
            if remaining <= 0:
                break
            take = min(layer.quantity_available, remaining)
            total_cost += take * layer.unit_cost
            layer.consume(take)
            remaining -= take
        if remaining > 0:
            raise ValueError("Insufficient stock layers to cover the requested quantity.")
        return total_cost, (total_cost / quantity) if quantity else Decimal("0")


class InventoryPostingService:
    """
    Handle inventory movement accounting with weighted-average costing.

    This service does not post journals itself; it returns the affected GL
    accounts so callers can create balanced JournalLines in their own
    transaction.
    """

    def __init__(self, *, organization):
        self.organization = organization

    def _build_calculator(self, *, product, warehouse, location, batch):
        return CostCalculator(
            organization=self.organization,
            product=product,
            warehouse=warehouse,
            location=location,
            batch=batch,
        )

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
        calculator = self._build_calculator(
            product=product, warehouse=warehouse, location=location, batch=batch
        )
        method = product.costing_method
        calculator = self._build_calculator(
            product=product, warehouse=warehouse, location=location, batch=batch
        )
        method = product.costing_method

        if method == CostingMethod.WEIGHTED_AVERAGE:
            current_qty = item.quantity_on_hand
            current_cost = item.unit_cost
            new_qty = current_qty + quantity

            if new_qty <= 0:
                raise ValueError("Receipt would drive on-hand to zero or negative; aborting.")

            total_existing_value = current_qty * current_cost
            total_new_value = quantity * unit_cost
            new_unit_cost = (total_existing_value + total_new_value) / new_qty
            ledger_unit_cost = new_unit_cost
        elif method in (CostingMethod.FIFO, CostingMethod.LIFO):
            ledger_unit_cost = unit_cost
            calculator.create_layer(quantity, unit_cost, reference_id)
        elif method == CostingMethod.STANDARD:
            ledger_unit_cost = product.standard_cost or unit_cost
        else:
            ledger_unit_cost = unit_cost

        item.quantity_on_hand += quantity
        item.updated_at = timezone.now()
        if method in (CostingMethod.WEIGHTED_AVERAGE, CostingMethod.STANDARD):
            item.unit_cost = ledger_unit_cost
            item.save(update_fields=["quantity_on_hand", "unit_cost", "updated_at"])
        else:
            item.save(update_fields=["quantity_on_hand", "updated_at"])

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
            unit_cost=ledger_unit_cost,
        )

        return InventoryPostingResult(
            quantity=quantity,
            unit_cost=ledger_unit_cost,
            total_cost=quantity * ledger_unit_cost,
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

        if method == CostingMethod.FIFO:
            total_cost, ledger_unit_cost = calculator.consume_layers(quantity, CostingMethod.FIFO)
        elif method == CostingMethod.LIFO:
            total_cost, ledger_unit_cost = calculator.consume_layers(quantity, CostingMethod.LIFO)
        elif method == CostingMethod.STANDARD:
            ledger_unit_cost = product.standard_cost or item.unit_cost
            total_cost = ledger_unit_cost * quantity
        else:
            ledger_unit_cost = item.unit_cost
            total_cost = ledger_unit_cost * quantity

        item.quantity_on_hand -= quantity
        item.updated_at = timezone.now()
        if method in (CostingMethod.WEIGHTED_AVERAGE, CostingMethod.STANDARD):
            item.unit_cost = ledger_unit_cost
            item.save(update_fields=["quantity_on_hand", "unit_cost", "updated_at"])
        else:
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
            unit_cost=ledger_unit_cost,
        )

        return InventoryPostingResult(
            quantity=quantity,
            unit_cost=ledger_unit_cost,
            total_cost=total_cost,
            inventory_item=item,
            ledger_entry=ledger,
            debit_account=cogs_account or product.expense_account,
            credit_account=product.inventory_account,
        )
