from django.db import transaction
from django.utils import timezone
from accounting.models import Organization
from inventory.models import Product, StockLedger, StockAdjustment


class InventoryService:
    """Service for managing inventory operations and stock ledger entries."""

    @staticmethod
    def create_stock_ledger_entry(organization, product, transaction_type, quantity,
                                unit_cost=None, total_cost=None, reference_doc=None,
                                reference_type=None, warehouse=None, batch=None, expiry_date=None):
        """
        Create a stock ledger entry for inventory transactions.

        Args:
            organization: Organization instance
            product: Product instance
            transaction_type: Type of transaction (IN/OUT/ADJUSTMENT)
            quantity: Quantity of the transaction
            unit_cost: Cost per unit (optional)
            total_cost: Total cost (optional)
            reference_doc: Reference document (optional)
            reference_type: Type of reference document (optional)
            warehouse: Warehouse location (optional)
            batch: Batch number (optional)
            expiry_date: Expiry date (optional)
        """
        try:
            # Calculate total cost if not provided
            if total_cost is None and unit_cost is not None:
                total_cost = unit_cost * abs(quantity)
            elif total_cost is None:
                total_cost = 0

            # Calculate unit cost if not provided
            if unit_cost is None and quantity != 0:
                unit_cost = total_cost / abs(quantity)
            elif unit_cost is None:
                unit_cost = 0

            # Create stock ledger entry
            stock_entry = StockLedger.objects.create(
                organization=organization,
                product=product,
                transaction_type=transaction_type,
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                reference_doc=reference_doc,
                reference_type=reference_type,
                warehouse=warehouse,
                batch=batch,
                expiry_date=expiry_date,
                transaction_date=timezone.now()
            )

            return stock_entry

        except Exception as e:
            raise Exception(f"Failed to create stock ledger entry: {str(e)}")

    @staticmethod
    def apply_stock_adjustment(organization, product, adjustment_type, quantity,
                             reason, reference_doc=None, warehouse=None):
        """
        Apply a stock adjustment to inventory.

        Args:
            organization: Organization instance
            product: Product instance
            adjustment_type: Type of adjustment (POSITIVE/NEGATIVE)
            quantity: Adjustment quantity
            reason: Reason for adjustment
            reference_doc: Reference document (optional)
            warehouse: Warehouse location (optional)
        """
        try:
            with transaction.atomic():
                # Create stock adjustment record
                adjustment = StockAdjustment.objects.create(
                    organization=organization,
                    product=product,
                    adjustment_type=adjustment_type,
                    quantity=quantity,
                    reason=reason,
                    reference_doc=reference_doc,
                    warehouse=warehouse,
                    adjustment_date=timezone.now()
                )

                # Create corresponding stock ledger entry
                transaction_type = 'IN' if adjustment_type == 'POSITIVE' else 'OUT'
                InventoryService.create_stock_ledger_entry(
                    organization=organization,
                    product=product,
                    transaction_type=transaction_type,
                    quantity=quantity if adjustment_type == 'POSITIVE' else -quantity,
                    reference_doc=reference_doc,
                    reference_type='STOCK_ADJUSTMENT',
                    warehouse=warehouse
                )

                return adjustment

        except Exception as e:
            raise Exception(f"Failed to apply stock adjustment: {str(e)}")

    @staticmethod
    def get_current_stock(organization, product, warehouse=None):
        """
        Get current stock level for a product.

        Args:
            organization: Organization instance
            product: Product instance
            warehouse: Warehouse location (optional)

        Returns:
            Current stock quantity
        """
        try:
            queryset = StockLedger.objects.filter(
                organization=organization,
                product=product
            )

            if warehouse:
                queryset = queryset.filter(warehouse=warehouse)

            # Sum all quantities (IN positive, OUT negative)
            total_quantity = queryset.aggregate(
                total=models.Sum('quantity')
            )['total'] or 0

            return total_quantity

        except Exception as e:
            raise Exception(f"Failed to get current stock: {str(e)}")


class WarehouseService:
    """
    Service for managing warehouses/godowns.
    """

    @staticmethod
    def get_warehouses_for_dropdown(organization):
        """
        Get active warehouses for dropdown selection filtered by organization.
        """
        from inventory.models import Warehouse
        warehouses = Warehouse.objects.filter(organization=organization, is_active=True).order_by('name')
        return [
            {'id': warehouse.id, 'name': warehouse.name}
            for warehouse in warehouses
        ]