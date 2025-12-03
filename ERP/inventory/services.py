import logging
from django.db import transaction
from django.utils import timezone
from django.db.models import F, DecimalField, Value, Case, When, ExpressionWrapper
from .models import StockLedger, InventoryItem, Batch, Product, Warehouse, Location
from accounting import services as accounting_services # Assuming accounting app has services

logger = logging.getLogger(__name__)

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
        for line in lines:
            product = Product.objects.get(organization=organization, code=line['product_code'])
            batch, _ = Batch.objects.get_or_create(
                organization=organization,
                product=product,
                batch_number=line.get('batch_number', 'N/A'), # Use 'N/A' or generate default if not provided
                serial_number=line.get('serial_number', '')
            )

            InventoryService.create_stock_ledger_entry(
                organization=organization,
                product=product,
                warehouse=warehouse,
                location=location,
                batch=batch,
                txn_type="purchase",
                reference_id=purchase_order.number, # Assuming PO has a 'number' field
                qty_in=line['qty'],
                unit_cost=line['cost']
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

# Add other services like SalesShipmentService, InventoryAdjustmentService etc.
