# Inventory/services/fulfillment_service.py
"""
Fulfillment services for pick, pack, ship workflows and backorder management
Supports distributor and retailer vertical playbooks
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from ..models import (
    PickList, PickListLine, PackingSlip, Shipment, Backorder,
    RMA, RMALine, TransitWarehouse, Product, Warehouse, Location,
    Batch, InventoryItem, StockLedger
)
from accounting.services.inventory_posting_service import InventoryPostingService


class PickPackShipService:
    """Service for managing the complete pick-pack-ship fulfillment workflow"""
    
    def __init__(self, organization):
        self.organization = organization
        self.posting_service = InventoryPostingService(organization)
    
    @transaction.atomic
    def create_pick_list(
        self,
        warehouse: Warehouse,
        order_reference: str,
        line_items: List[Dict],
        priority: int = 5,
        assigned_to: Optional[int] = None
    ) -> PickList:
        """
        Create a pick list for warehouse picking
        
        Args:
            warehouse: Warehouse to pick from
            order_reference: Sales order or transfer order number
            line_items: List of dicts with 'product_id', 'quantity', 'location_id', 'batch_id'
            priority: 1=urgent, 10=low
            assigned_to: User ID of assigned picker
        
        Returns:
            PickList instance
        """
        # Generate pick number
        prefix = f"PL-{warehouse.code}"
        last_pick = PickList.objects.filter(
            organization=self.organization,
            pick_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_pick:
            last_num = int(last_pick.pick_number.split('-')[-1])
            pick_number = f"{prefix}-{last_num + 1:06d}"
        else:
            pick_number = f"{prefix}-000001"
        
        # Create pick list
        pick_list = PickList.objects.create(
            organization=self.organization,
            pick_number=pick_number,
            warehouse=warehouse,
            order_reference=order_reference,
            status='draft',
            priority=priority,
            assigned_to=assigned_to
        )
        
        # Create line items
        for idx, item in enumerate(line_items, start=1):
            product = Product.objects.get(id=item['product_id'], organization=self.organization)
            location = Location.objects.get(id=item['location_id']) if item.get('location_id') else None
            batch = Batch.objects.get(id=item['batch_id']) if item.get('batch_id') else None
            
            PickListLine.objects.create(
                pick_list=pick_list,
                product=product,
                location=location,
                batch=batch,
                quantity_ordered=Decimal(str(item['quantity'])),
                line_number=idx
            )
        
        return pick_list
    
    @transaction.atomic
    def release_pick_list(self, pick_list: PickList) -> bool:
        """Release pick list to warehouse floor"""
        if pick_list.status != 'draft':
            raise ValueError(f"Cannot release pick list in {pick_list.status} status")
        
        pick_list.status = 'released'
        pick_list.pick_date = timezone.now()
        pick_list.save()
        return True
    
    @transaction.atomic
    def record_pick(
        self,
        pick_list: PickList,
        line_number: int,
        quantity_picked: Decimal,
        picked_by: int
    ) -> PickListLine:
        """Record picked quantity for a line item"""
        line = PickListLine.objects.get(pick_list=pick_list, line_number=line_number)
        
        if quantity_picked > line.quantity_ordered:
            raise ValueError(f"Picked quantity {quantity_picked} exceeds ordered {line.quantity_ordered}")
        
        line.quantity_picked = quantity_picked
        line.picked_by = picked_by
        line.picked_at = timezone.now()
        line.save()
        
        # Update pick list status if picking started
        if pick_list.status == 'released':
            pick_list.status = 'picking'
            pick_list.save()
        
        # Check if all lines are picked
        all_picked = all(
            line.quantity_picked >= line.quantity_ordered
            for line in pick_list.lines.all()
        )
        
        if all_picked:
            pick_list.status = 'picked'
            pick_list.completed_date = timezone.now()
            pick_list.save()
        
        return line
    
    @transaction.atomic
    def create_packing_slip(
        self,
        pick_list: PickList,
        num_packages: int = 1,
        total_weight: Optional[Decimal] = None,
        packed_by: Optional[int] = None
    ) -> PackingSlip:
        """Create packing slip from completed pick list"""
        if pick_list.status != 'picked':
            raise ValueError(f"Pick list must be in 'picked' status, currently {pick_list.status}")
        
        # Generate packing number
        prefix = f"PS-{pick_list.warehouse.code}"
        last_pack = PackingSlip.objects.filter(
            organization=self.organization,
            packing_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_pack:
            last_num = int(last_pack.packing_number.split('-')[-1])
            packing_number = f"{prefix}-{last_num + 1:06d}"
        else:
            packing_number = f"{prefix}-000001"
        
        packing_slip = PackingSlip.objects.create(
            organization=self.organization,
            packing_number=packing_number,
            pick_list=pick_list,
            warehouse=pick_list.warehouse,
            order_reference=pick_list.order_reference,
            status='packing',
            packed_by=packed_by,
            num_packages=num_packages,
            total_weight=total_weight
        )
        
        return packing_slip
    
    @transaction.atomic
    def complete_packing(self, packing_slip: PackingSlip) -> bool:
        """Mark packing as complete"""
        if packing_slip.status not in ['draft', 'packing']:
            raise ValueError(f"Cannot complete packing in {packing_slip.status} status")
        
        packing_slip.status = 'packed'
        packing_slip.packed_date = timezone.now()
        packing_slip.save()
        return True
    
    @transaction.atomic
    def create_shipment(
        self,
        packing_slip: PackingSlip,
        carrier_name: str,
        ship_to_address: str,
        tracking_number: str = '',
        service_type: str = '',
        estimated_delivery: Optional[str] = None,
        shipping_cost: Optional[Decimal] = None
    ) -> Shipment:
        """Create shipment for packed goods"""
        if packing_slip.status != 'packed':
            raise ValueError(f"Packing slip must be packed, currently {packing_slip.status}")
        
        # Generate shipment number
        prefix = f"SH-{packing_slip.warehouse.code}"
        last_ship = Shipment.objects.filter(
            organization=self.organization,
            shipment_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_ship:
            last_num = int(last_ship.shipment_number.split('-')[-1])
            shipment_number = f"{prefix}-{last_num + 1:06d}"
        else:
            shipment_number = f"{prefix}-000001"
        
        shipment = Shipment.objects.create(
            organization=self.organization,
            shipment_number=shipment_number,
            packing_slip=packing_slip,
            order_reference=packing_slip.order_reference,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
            service_type=service_type,
            status='pending',
            ship_from_warehouse=packing_slip.warehouse,
            ship_to_address=ship_to_address,
            estimated_delivery=estimated_delivery,
            shipping_cost=shipping_cost
        )
        
        # Post inventory reduction
        self._post_shipment_inventory(shipment)
        
        return shipment
    
    def _post_shipment_inventory(self, shipment: Shipment):
        """Post inventory transactions for shipment"""
        if not shipment.packing_slip or not shipment.packing_slip.pick_list:
            return
        
        pick_list = shipment.packing_slip.pick_list
        
        for line in pick_list.lines.all():
            if line.quantity_picked > 0:
                # Issue stock from warehouse
                self.posting_service.post_stock_issue(
                    product=line.product,
                    warehouse=pick_list.warehouse,
                    location=line.location,
                    batch=line.batch,
                    quantity=line.quantity_picked,
                    reference_id=shipment.shipment_number,
                    txn_date=timezone.now()
                )
    
    @transaction.atomic
    def update_shipment_status(
        self,
        shipment: Shipment,
        new_status: str,
        actual_delivery: Optional[str] = None
    ) -> Shipment:
        """Update shipment tracking status"""
        valid_statuses = dict(Shipment.STATUS_CHOICES).keys()
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")
        
        shipment.status = new_status
        
        if new_status == 'delivered' and actual_delivery:
            shipment.actual_delivery = actual_delivery
        
        shipment.save()
        return shipment


class BackorderService:
    """Service for managing backorders and partial fulfillment"""
    
    def __init__(self, organization):
        self.organization = organization
    
    @transaction.atomic
    def create_backorder(
        self,
        order_reference: str,
        product: Product,
        warehouse: Warehouse,
        quantity_backordered: Decimal,
        customer_id: Optional[int] = None,
        expected_date: Optional[str] = None,
        priority: int = 5
    ) -> Backorder:
        """Create a backorder record"""
        # Generate backorder number
        prefix = "BO"
        last_bo = Backorder.objects.filter(
            organization=self.organization,
            backorder_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_bo:
            last_num = int(last_bo.backorder_number.split('-')[-1])
            backorder_number = f"{prefix}-{last_num + 1:06d}"
        else:
            backorder_number = f"{prefix}-000001"
        
        backorder = Backorder.objects.create(
            organization=self.organization,
            backorder_number=backorder_number,
            order_reference=order_reference,
            product=product,
            warehouse=warehouse,
            quantity_backordered=quantity_backordered,
            customer_id=customer_id,
            expected_date=expected_date,
            priority=priority
        )
        
        return backorder
    
    @transaction.atomic
    def fulfill_backorder(
        self,
        backorder: Backorder,
        quantity_to_fulfill: Decimal
    ) -> Tuple[Backorder, bool]:
        """
        Fulfill part or all of a backorder
        
        Returns:
            Tuple of (backorder, is_fully_fulfilled)
        """
        if quantity_to_fulfill > backorder.quantity_remaining:
            raise ValueError(
                f"Fulfillment quantity {quantity_to_fulfill} exceeds remaining {backorder.quantity_remaining}"
            )
        
        backorder.quantity_fulfilled += quantity_to_fulfill
        
        if backorder.quantity_fulfilled >= backorder.quantity_backordered:
            backorder.is_fulfilled = True
        
        backorder.save()
        
        return backorder, backorder.is_fulfilled
    
    def get_active_backorders(
        self,
        product: Optional[Product] = None,
        warehouse: Optional[Warehouse] = None,
        priority: Optional[int] = None
    ) -> List[Backorder]:
        """Get active backorders with optional filters"""
        queryset = Backorder.objects.filter(
            organization=self.organization,
            is_fulfilled=False
        )
        
        if product:
            queryset = queryset.filter(product=product)
        
        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        
        if priority is not None:
            queryset = queryset.filter(priority=priority)
        
        return list(queryset.order_by('priority', 'created_at'))
    
    def check_backorder_fulfillment_availability(
        self,
        backorder: Backorder
    ) -> Decimal:
        """
        Check how much of a backorder can be fulfilled with current inventory
        
        Returns:
            Available quantity that can fulfill the backorder
        """
        inventory_items = InventoryItem.objects.filter(
            organization=self.organization,
            product=backorder.product,
            warehouse=backorder.warehouse,
            quantity_on_hand__gt=0
        )
        
        total_available = sum(item.quantity_on_hand for item in inventory_items)
        quantity_remaining = backorder.quantity_remaining
        
        return min(total_available, quantity_remaining)


class RMAService:
    """Service for managing Return Merchandise Authorization"""
    
    def __init__(self, organization):
        self.organization = organization
        self.posting_service = InventoryPostingService(organization)
    
    @transaction.atomic
    def create_rma(
        self,
        customer_id: int,
        original_order: str,
        reason: str,
        description: str,
        line_items: List[Dict],
        original_invoice: str = '',
        warehouse: Optional[Warehouse] = None
    ) -> RMA:
        """
        Create RMA request
        
        Args:
            customer_id: Customer ID
            original_order: Original sales order number
            reason: Return reason code
            description: Detailed description
            line_items: List of dicts with 'product_id', 'quantity', 'batch_id', 'condition'
            original_invoice: Original invoice number
            warehouse: Receiving warehouse
        """
        # Generate RMA number
        prefix = "RMA"
        last_rma = RMA.objects.filter(
            organization=self.organization,
            rma_number__startswith=prefix
        ).order_by('-id').first()
        
        if last_rma:
            last_num = int(last_rma.rma_number.split('-')[-1])
            rma_number = f"{prefix}-{last_num + 1:06d}"
        else:
            rma_number = f"{prefix}-000001"
        
        rma = RMA.objects.create(
            organization=self.organization,
            rma_number=rma_number,
            customer_id=customer_id,
            original_order=original_order,
            original_invoice=original_invoice,
            status='requested',
            reason=reason,
            description=description,
            warehouse=warehouse
        )
        
        # Create line items
        for idx, item in enumerate(line_items, start=1):
            product = Product.objects.get(id=item['product_id'], organization=self.organization)
            batch = Batch.objects.get(id=item['batch_id']) if item.get('batch_id') else None
            
            RMALine.objects.create(
                rma=rma,
                product=product,
                quantity_returned=Decimal(str(item['quantity'])),
                batch=batch,
                condition=item.get('condition', ''),
                line_number=idx
            )
        
        return rma
    
    @transaction.atomic
    def approve_rma(
        self,
        rma: RMA,
        approved_by: int,
        resolution: str,
        refund_amount: Optional[Decimal] = None,
        restocking_fee: Decimal = Decimal('0')
    ) -> RMA:
        """Approve RMA request"""
        if rma.status != 'requested':
            raise ValueError(f"Cannot approve RMA in {rma.status} status")
        
        rma.status = 'approved'
        rma.approved_date = timezone.now()
        rma.approved_by = approved_by
        rma.resolution = resolution
        rma.refund_amount = refund_amount
        rma.restocking_fee = restocking_fee
        rma.save()
        
        return rma
    
    @transaction.atomic
    def receive_rma(
        self,
        rma: RMA,
        warehouse: Warehouse,
        location: Optional[Location] = None
    ) -> RMA:
        """Receive returned goods into warehouse"""
        if rma.status != 'approved':
            raise ValueError(f"Cannot receive RMA in {rma.status} status")
        
        # Post inventory receipts for items to be restocked
        for line in rma.lines.all():
            if line.disposition == 'restock':
                self.posting_service.post_stock_receipt(
                    product=line.product,
                    warehouse=warehouse,
                    location=location,
                    batch=line.batch,
                    quantity=line.quantity_returned,
                    unit_cost=Decimal('0'),  # RMA returns at zero cost
                    reference_id=rma.rma_number,
                    txn_date=timezone.now()
                )
        
        rma.status = 'received'
        rma.warehouse = warehouse
        rma.save()
        
        return rma
    
    @transaction.atomic
    def close_rma(self, rma: RMA) -> RMA:
        """Close completed RMA"""
        if rma.status not in ['received', 'inspected', 'refunded', 'replaced']:
            raise ValueError(f"Cannot close RMA in {rma.status} status")
        
        rma.status = 'closed'
        rma.save()
        
        return rma
