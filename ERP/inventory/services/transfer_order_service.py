from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounting.models import Organization
from inventory.models import TransferOrder, TransferOrderLine, Warehouse, Product, Location, Batch


class TransferOrderService:
    """Service for managing transfer orders between warehouses."""

    def __init__(self, organization):
        self.organization = organization

    def create_transfer_order(self, order_number, source_warehouse, destination_warehouse,
                            lines_data, scheduled_date=None, reference_id='', notes='',
                            instructions='', requested_by=None):
        """
        Create a new transfer order.

        Args:
            order_number: Unique order number
            source_warehouse: Source warehouse
            destination_warehouse: Destination warehouse
            lines_data: List of line items with product, quantity, etc.
            scheduled_date: Scheduled transfer date (optional)
            reference_id: Reference ID (optional)
            notes: Notes (optional)
            instructions: Transfer instructions (optional)
            requested_by: User requesting the transfer (optional)

        Returns:
            Created TransferOrder instance
        """
        try:
            with transaction.atomic():
                # Create transfer order
                transfer_order = TransferOrder.objects.create(
                    organization=self.organization,
                    order_number=order_number,
                    source_warehouse=source_warehouse,
                    destination_warehouse=destination_warehouse,
                    scheduled_date=scheduled_date,
                    reference_id=reference_id,
                    notes=notes,
                    instructions=instructions,
                    created_by=requested_by
                )

                # Create transfer order lines
                for line_data in lines_data:
                    TransferOrderLine.objects.create(
                        transfer_order=transfer_order,
                        product=line_data['product'],
                        from_location=line_data.get('from_location'),
                        to_location=line_data.get('to_location'),
                        batch=line_data.get('batch'),
                        quantity_requested=line_data['quantity']
                    )

                return transfer_order

        except Exception as e:
            raise Exception(f"Failed to create transfer order: {str(e)}")

    def release_transfer_order(self, transfer_order, approved_by=None):
        """
        Release a transfer order for processing.

        Args:
            transfer_order: TransferOrder instance
            approved_by: User approving the release (optional)

        Returns:
            Updated TransferOrder instance
        """
        try:
            if transfer_order.status != 'draft':
                raise ValidationError(f"Cannot release transfer order with status: {transfer_order.status}")

            transfer_order.status = 'released'
            transfer_order.approved_by = approved_by
            transfer_order.save()

            return transfer_order

        except Exception as e:
            raise Exception(f"Failed to release transfer order: {str(e)}")

    def update_transfer_status(self, transfer_order, new_status, updated_by=None):
        """
        Update the status of a transfer order.

        Args:
            transfer_order: TransferOrder instance
            new_status: New status value
            updated_by: User updating the status (optional)

        Returns:
            Updated TransferOrder instance
        """
        try:
            valid_statuses = ['draft', 'released', 'in_transit', 'received', 'cancelled']
            if new_status not in valid_statuses:
                raise ValidationError(f"Invalid status: {new_status}")

            # Validate status transitions
            current_status = transfer_order.status
            if current_status == 'cancelled':
                raise ValidationError("Cannot change status of cancelled transfer order")
            if current_status == 'received' and new_status != 'received':
                raise ValidationError("Cannot change status of received transfer order")

            transfer_order.status = new_status
            transfer_order.save()

            return transfer_order

        except Exception as e:
            raise Exception(f"Failed to update transfer order status: {str(e)}")

    def get_transfer_orders(self, status=None, source_warehouse=None, destination_warehouse=None):
        """
        Get transfer orders with optional filtering.

        Args:
            status: Filter by status (optional)
            source_warehouse: Filter by source warehouse (optional)
            destination_warehouse: Filter by destination warehouse (optional)

        Returns:
            QuerySet of TransferOrder instances
        """
        try:
            queryset = TransferOrder.objects.filter(organization=self.organization)

            if status:
                queryset = queryset.filter(status=status)
            if source_warehouse:
                queryset = queryset.filter(source_warehouse=source_warehouse)
            if destination_warehouse:
                queryset = queryset.filter(destination_warehouse=destination_warehouse)

            return queryset.order_by('-created_at')

        except Exception as e:
            raise Exception(f"Failed to get transfer orders: {str(e)}")

    def get_transfer_order_details(self, transfer_order_id):
        """
        Get detailed information about a transfer order including lines.

        Args:
            transfer_order_id: TransferOrder ID

        Returns:
            TransferOrder instance with prefetched lines
        """
        try:
            return TransferOrder.objects.prefetch_related('lines__product').get(
                id=transfer_order_id,
                organization=self.organization
            )

        except TransferOrder.DoesNotExist:
            raise Exception(f"Transfer order not found: {transfer_order_id}")
        except Exception as e:
            raise Exception(f"Failed to get transfer order details: {str(e)}")