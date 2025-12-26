from .models import VendorPriceHistory, CustomerPriceHistory
from accounting.models import Vendor, Customer
from usermanagement.models import CustomUser
import logging
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from django.db import transaction
from django.utils import timezone
from django.db.models import F, DecimalField, Value, Case, When, ExpressionWrapper

from .models import StockLedger, InventoryItem, Batch, Product, Warehouse, Location, TransferOrder, TransferOrderLine
import importlib.util
from pathlib import Path

# Load the legacy utils module by file path to avoid the package name conflict (inventory.utils package exists).
_utils_path = Path(__file__).resolve().parent / "utils.py"
_utils_spec = importlib.util.spec_from_file_location("inventory_raw_utils", _utils_path)
inventory_utils = importlib.util.module_from_spec(_utils_spec)
inventory_utils.__package__ = 'inventory'
_utils_spec.loader.exec_module(inventory_utils)
from accounting import services as accounting_services  # Assuming accounting app has services

logger = logging.getLogger(__name__)


class PriceHistoryService:
    @staticmethod
    def record_vendor_price_history(vendor, product, unit_price, doc_date, organization, created_by=None, document_type=None, document_id=None):
        """Record a vendor purchase rate history entry."""
        return VendorPriceHistory.objects.create(
            organization=organization,
            vendor=vendor,
            product=product,
            purchase_rate=unit_price,
            doc_date=doc_date,
            created_by=created_by,
            document_type=document_type,
            document_id=document_id
        )

    @staticmethod
    def record_customer_price_history(customer, product, unit_price, doc_date, organization, created_by=None, document_type=None, document_id=None):
        """Record a customer sales rate history entry."""
        return CustomerPriceHistory.objects.create(
            organization=organization,
            customer=customer,
            product=product,
            sales_rate=unit_price,
            doc_date=doc_date,
            created_by=created_by,
            document_type=document_type,
            document_id=document_id
        )

    @staticmethod
    def get_vendor_price_history(organization, product, vendor=None, limit=20):
        qs = VendorPriceHistory.objects.filter(organization=organization, product=product)
        if vendor:
            qs = qs.filter(vendor=vendor)
        return qs.order_by('-doc_date')[:limit]

    @staticmethod
    def get_customer_price_history(organization, product, customer=None, limit=20):
        qs = CustomerPriceHistory.objects.filter(organization=organization, product=product)
        if customer:
            qs = qs.filter(customer=customer)
        return qs.order_by('-doc_date')[:limit]


class InventoryService:
    @staticmethod
    @transaction.atomic
    def create_stock_ledger_entry(
        organization,
        product,
        warehouse,
        location,
        batch,
        txn_type,
        reference_id,
        qty_in=0,
        qty_out=0,
        unit_cost=0,
        txn_date=None,
        async_ledger=True,
    ):
        """Creates a StockLedger entry and updates InventoryItem.

        When ``async_ledger`` is True the StockLedger row is queued for creation
        after the surrounding transaction commits, reducing lock contention on
        "hot" inventory rows during heavy checkout traffic.
        """
        if not txn_date:
            txn_date = timezone.now()

        ledger_kwargs = {
            "organization": organization,
            "product": product,
            "warehouse": warehouse,
            "location": location,
            "batch": batch,
            "txn_type": txn_type,
            "reference_id": reference_id,
            "txn_date": txn_date,
            "qty_in": qty_in,
            "qty_out": qty_out,
            "unit_cost": unit_cost,
        }

        inventory_item, created = InventoryItem.objects.get_or_create(
            organization=organization,
            product=product,
            warehouse=warehouse,
            location=location, # Include location in unique key for granular tracking
            batch=batch,       # Include batch in unique key
            defaults={'quantity_on_hand': Decimal('0'), 'unit_cost': unit_cost}
        )

        quantity_delta = qty_in - qty_out
        update_kwargs = {
            "quantity_on_hand": F('quantity_on_hand') + quantity_delta
        }

        if qty_in > 0:
            moving_average = ExpressionWrapper(
                (F('quantity_on_hand') * F('unit_cost') + Value(qty_in) * Value(unit_cost)) /
                (F('quantity_on_hand') + Value(qty_in)),
                output_field=DecimalField(max_digits=19, decimal_places=4),
            )

            update_kwargs["unit_cost"] = Case(
                When(quantity_on_hand__gt=0, then=moving_average),
                default=Value(unit_cost),
                output_field=DecimalField(max_digits=19, decimal_places=4),
            )

        InventoryItem.objects.filter(pk=inventory_item.pk).update(**update_kwargs)
        inventory_item.refresh_from_db() # Get updated values after F() expression

        def _create_ledger_entry():
            StockLedger.objects.create(**ledger_kwargs)

        if async_ledger:
            transaction.on_commit(_create_ledger_entry)
            ledger_entry = None
        else:
            ledger_entry = StockLedger.objects.create(**ledger_kwargs)

        logger.info(
            f"Inventory update: Txn={txn_type}, Ref={reference_id}, "
            f"Product={product.code}, Wh={warehouse.code}, Loc={location.code if location else 'N/A'}, "
            f"Batch={batch.batch_number if batch else 'N/A'}, "
            f"QtyIn={qty_in}, QtyOut={qty_out}, Cost={unit_cost}, "
            f"New QOH={inventory_item.quantity_on_hand}, New Cost={inventory_item.unit_cost}"
        )

        return ledger_entry, inventory_item

    @staticmethod
    @transaction.atomic
    def apply_stock_adjustment(
        organization,
        product,
        warehouse,
        location,
        batch,
        counted_quantity,
        reference_id,
    ):
        """Apply a manual stock adjustment line and post a ledger entry."""
        inventory_item = InventoryItem.objects.filter(
            organization=organization,
            product=product,
            warehouse=warehouse,
            location=location,
            batch=batch,
        ).first()

        system_quantity = inventory_item.quantity_on_hand if inventory_item else Decimal('0')
        unit_cost = (
            inventory_item.unit_cost
            if inventory_item and inventory_item.unit_cost
            else product.cost_price
        ) or Decimal('0')

        quantity_delta = counted_quantity - system_quantity
        if quantity_delta == 0:
            return {
                'inventory_item': inventory_item,
                'system_quantity': system_quantity,
                'unit_cost': unit_cost,
                'quantity_delta': Decimal('0'),
                'ledger_entry': None,
            }

        txn_type = 'adjustment_receipt' if quantity_delta > 0 else 'adjustment_issue'
        qty_in = quantity_delta if quantity_delta > 0 else Decimal('0')
        qty_out = -quantity_delta if quantity_delta < 0 else Decimal('0')

        ledger_entry, inventory_item = InventoryService.create_stock_ledger_entry(
            organization=organization,
            product=product,
            warehouse=warehouse,
            location=location,
            batch=batch,
            txn_type=txn_type,
            reference_id=reference_id,
            qty_in=qty_in,
            qty_out=qty_out,
            unit_cost=unit_cost,
            async_ledger=False,
        )

        return {
            'inventory_item': inventory_item,
            'system_quantity': system_quantity,
            'unit_cost': unit_cost,
            'quantity_delta': quantity_delta,
            'ledger_entry': ledger_entry,
        }

class PurchaseReceiptService:
    @staticmethod
    @transaction.atomic
    def receive(purchase_order, lines, warehouse_code, location_code=None):
        """Processes a purchase receipt."""
        organization = purchase_order.organization
        warehouse = Warehouse.objects.get(organization=organization, code=warehouse_code)
        location = None
        if location_code:
            location = Location.objects.get(warehouse=warehouse, code=location_code)

        # Assuming 'lines' is an iterable of objects/dicts with product, qty, cost, batch_number, serial_number

        user = getattr(purchase_order, 'created_by', None)
        vendor = getattr(purchase_order, 'vendor', None)
        doc_date = getattr(purchase_order, 'order_date', timezone.now().date())
        doc_ref = getattr(purchase_order, 'number', None)

        for line in lines:
            product = Product.objects.get(organization=organization, code=line['product_code'])
            batch, _ = Batch.objects.get_or_create(
                organization=organization,
                product=product,
                batch_number=line.get('batch_number', 'N/A'),
                serial_number=line.get('serial_number', '')
            )

            InventoryService.create_stock_ledger_entry(
                organization=organization,
                product=product,
                warehouse=warehouse,
                location=location,
                batch=batch,
                txn_type="purchase",
                reference_id=purchase_order.number,
                qty_in=line['qty'],
                unit_cost=line['cost']
            )

            # Record vendor price history
            if vendor:
                from .services import PriceHistoryService
                PriceHistoryService.record_vendor_price_history(
                    organization=organization,
                    vendor=vendor,
                    product=product,
                    rate=line['cost'],
                    currency=getattr(purchase_order, 'currency', 'USD'),
                    quantity=line['qty'],
                    doc_ref=doc_ref,
                    doc_date=doc_date,
                    user=user
                )

        # Call accounting service (placeholder)
        # accounting_services.grir_to_inventory(purchase_order)
        logger.info(f"Processed purchase receipt for PO {purchase_order.number} at warehouse {warehouse.code}")

class TransferService:
    @staticmethod
    @transaction.atomic
    def move(organization, product_code, from_warehouse_code, from_location_code, to_warehouse_code, to_location_code, qty, batch_number=None, serial_number=None):
        """Processes an internal stock transfer."""
        product = Product.objects.get(organization=organization, code=product_code)
        from_warehouse = Warehouse.objects.get(organization=organization, code=from_warehouse_code)
        from_location = Location.objects.get(warehouse=from_warehouse, code=from_location_code)
        to_warehouse = Warehouse.objects.get(organization=organization, code=to_warehouse_code)
        to_location = Location.objects.get(warehouse=to_warehouse, code=to_location_code)

        batch = None
        if batch_number:
             batch = Batch.objects.get(organization=organization, product=product, batch_number=batch_number, serial_number=serial_number or '')

        # Get the unit cost from the source InventoryItem before moving
        try:
            source_item = InventoryItem.objects.get(
                 organization=organization,
                 product=product,
                 warehouse=from_warehouse,
                 location=from_location,
                 batch=batch
            )
            unit_cost = source_item.unit_cost
        except InventoryItem.DoesNotExist:
            # Handle case where item doesn't exist at source location/batch
            logger.warning(f"Attempted to move non-existent item: {product.code} from {from_warehouse.code}/{from_location.code}")
            # Decide how to handle: raise error, use product cost, etc.
            # For now, let's use product cost as a fallback
            unit_cost = product.cost_price

        # Create OUT ledger entry at source
        InventoryService.create_stock_ledger_entry(
            organization=organization,
            product=product,
            warehouse=from_warehouse,
            location=from_location,
            batch=batch,
            txn_type="transfer_out",
            reference_id=f"MOVE-{timezone.now().strftime('%Y%m%d%H%M%S')}", # Generate a unique ref
            qty_out=qty,
            unit_cost=unit_cost # Use cost from source
        )

        # Create IN ledger entry at destination
        InventoryService.create_stock_ledger_entry(
            organization=organization,
            product=product,
            warehouse=to_warehouse,
            location=to_location,
            batch=batch,
            txn_type="transfer_in",
            reference_id=f"MOVE-{timezone.now().strftime('%Y%m%d%H%M%S')}", # Use the same ref
            qty_in=qty,
            unit_cost=unit_cost # Use cost from source
        )

        logger.info(f"Processed transfer of {qty} x {product.code} from {from_warehouse.code}/{from_location.code} to {to_warehouse.code}/{to_location.code}")


class TransferOrderService:
    """Service to manage transfer order lifecycle and posting."""

    def __init__(self, organization):
        self.organization = organization

    @transaction.atomic
    def release_order(self, order: TransferOrder) -> TransferOrder:
        if order.status != 'draft':
            raise ValueError("Only draft transfer orders can be released.")
        order.status = 'released'
        order.save(update_fields=['status', 'updated_at'])
        return order

    @transaction.atomic
    def execute_transfer(self, order: TransferOrder) -> Tuple[TransferOrder, List[TransferOrderLine]]:
        if order.status not in ['released', 'in_transit']:
            raise ValueError("Transfer order must be released before execution.")

        reference = order.reference_id or order.order_number
        transferred_lines = []

        for line in order.lines.select_related('product').all():
            if line.quantity_requested <= 0:
                continue

            success, message = inventory_utils.WarehouseService.transfer_stock(
                from_warehouse=order.source_warehouse,
                to_warehouse=order.destination_warehouse,
                product=line.product,
                quantity=line.quantity_requested,
                from_location=line.from_location,
                to_location=line.to_location,
                batch=line.batch,
                reference_id=f"{reference}-{line.pk}",
                user=order.created_by
            )

            if not success:
                raise ValueError(f"Line {line.pk}: {message}")

            line.quantity_transferred = line.quantity_requested
            line.status = 'transferred'
            line.save(update_fields=['quantity_transferred', 'status'])
            transferred_lines.append(line)

        order.status = 'received'
        order.save(update_fields=['status', 'updated_at'])
        return order, transferred_lines
# Add other services like SalesShipmentService, InventoryAdjustmentService etc.
