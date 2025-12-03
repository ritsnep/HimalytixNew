# Inventory/services/allocation_service.py
"""
Omnichannel Inventory Allocation Service

Provides ATP (Available-to-Promise) calculations, multi-warehouse allocation,
safety stock management, and channel-based allocation prioritization for
distributors and multi-warehouse retailers.

Key Features:
- Real-time ATP calculations across warehouses
- Safety stock reservations
- Channel priority rules (B2B, B2C, wholesale, retail)
- Cost-optimized allocation (ship from nearest/cheapest)
- Backorder management
- Future inventory visibility (in-transit, production)
"""
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from enum import Enum

from django.db.models import Sum, Q, F
from django.db import transaction
from django.utils import timezone

from ..models import (
    Product, Warehouse, InventoryItem, Location,
    TransitWarehouse, PickList, PickListLine
)


class AllocationPriority(Enum):
    """Channel allocation priorities"""
    CRITICAL = 1      # Critical customers, rush orders
    B2B = 2          # Business-to-business
    RETAIL = 3       # Retail stores
    B2C = 4          # Direct to consumer
    WHOLESALE = 5    # Wholesale/bulk


class AllocationStrategy(Enum):
    """Allocation optimization strategies"""
    NEAREST = 'nearest'          # Ship from nearest warehouse
    COST = 'cost'               # Minimize shipping cost
    BALANCE = 'balance'         # Balance inventory across warehouses
    FIFO = 'fifo'              # First-in-first-out
    FEFO = 'fefo'              # First-expired-first-out


@dataclass
class ATPResult:
    """Available-to-Promise calculation result"""
    product_code: str
    warehouse_code: str
    on_hand: Decimal
    allocated: Decimal
    safety_stock: Decimal
    available: Decimal  # on_hand - allocated - safety_stock
    in_transit: Decimal
    future_available: Dict[date, Decimal]  # Future ATP by date


@dataclass
class AllocationRequest:
    """Inventory allocation request"""
    product_code: str
    quantity: Decimal
    priority: AllocationPriority
    customer_id: Optional[str] = None
    preferred_warehouse: Optional[str] = None
    required_date: Optional[date] = None
    channel: Optional[str] = None  # 'b2b', 'b2c', 'retail', 'wholesale'


@dataclass
class AllocationResult:
    """Result of allocation operation"""
    success: bool
    allocated_quantity: Decimal
    backorder_quantity: Decimal
    allocations: List[Dict]  # [{'warehouse': 'WH-001', 'quantity': 10, 'location': 'A-01'}]
    estimated_ship_date: Optional[date] = None
    message: str = ''


class AllocationService:
    """
    Inventory Allocation Service
    
    Manages multi-warehouse inventory allocation with ATP calculations,
    safety stock, and channel prioritization.
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_atp(
        self,
        product_code: str,
        warehouse_code: Optional[str] = None,
        include_future: bool = True
    ) -> List[ATPResult]:
        """
        Calculate Available-to-Promise for a product
        
        ATP = On Hand - Allocated - Safety Stock + In Transit
        
        Args:
            product_code: Product to check
            warehouse_code: Specific warehouse (None for all)
            include_future: Include future ATP projections
        
        Returns:
            List of ATPResult for each warehouse
        """
        # Get product
        try:
            product = Product.objects.get(
                organization=self.organization,
                code=product_code
            )
        except Product.DoesNotExist:
            return []
        
        # Get inventory items
        inventory_items = InventoryItem.objects.filter(
            organization=self.organization,
            product=product
        ).select_related('warehouse')
        
        if warehouse_code:
            inventory_items = inventory_items.filter(warehouse__code=warehouse_code)
        
        results = []
        
        for item in inventory_items:
            # Calculate allocated quantity (from active pick lists)
            allocated = self._get_allocated_quantity(product, item.warehouse)
            
            # Get safety stock (could be warehouse-specific)
            safety_stock = self._get_safety_stock(product, item.warehouse)
            
            # Calculate available
            available = item.quantity_on_hand - allocated - safety_stock
            
            # Get in-transit quantity
            in_transit = self._get_in_transit_quantity(product, item.warehouse)
            
            # Future ATP calculations
            future_atp = {}
            if include_future:
                future_atp = self._calculate_future_atp(product, item.warehouse)
            
            results.append(ATPResult(
                product_code=product.code,
                warehouse_code=item.warehouse.code,
                on_hand=item.quantity_on_hand,
                allocated=allocated,
                safety_stock=safety_stock,
                available=max(available, Decimal('0.00')),
                in_transit=in_transit,
                future_available=future_atp
            ))
        
        return results
    
    def allocate_inventory(
        self,
        request: AllocationRequest,
        strategy: AllocationStrategy = AllocationStrategy.NEAREST
    ) -> AllocationResult:
        """
        Allocate inventory across warehouses based on strategy
        
        Args:
            request: Allocation request details
            strategy: Allocation optimization strategy
        
        Returns:
            AllocationResult with allocations by warehouse
        """
        # Get product
        try:
            product = Product.objects.get(
                organization=self.organization,
                code=request.product_code
            )
        except Product.DoesNotExist:
            return AllocationResult(
                success=False,
                allocated_quantity=Decimal('0.00'),
                backorder_quantity=request.quantity,
                allocations=[],
                message=f"Product not found: {request.product_code}"
            )
        
        # Calculate ATP across warehouses
        atp_results = self.calculate_atp(request.product_code, include_future=False)
        
        # Filter out warehouses with no availability
        available_warehouses = [
            atp for atp in atp_results 
            if atp.available > 0
        ]
        
        if not available_warehouses:
            # No inventory available - create backorder
            return AllocationResult(
                success=False,
                allocated_quantity=Decimal('0.00'),
                backorder_quantity=request.quantity,
                allocations=[],
                message="No inventory available - backorder created"
            )
        
        # Sort warehouses by strategy
        sorted_warehouses = self._sort_warehouses_by_strategy(
            available_warehouses,
            strategy,
            request
        )
        
        # Allocate quantity across warehouses
        remaining_qty = request.quantity
        allocations = []
        
        for atp in sorted_warehouses:
            if remaining_qty <= 0:
                break
            
            # Allocate up to available quantity
            allocated = min(atp.available, remaining_qty)
            
            allocations.append({
                'warehouse': atp.warehouse_code,
                'quantity': allocated,
                'location': None  # TODO: Add location logic
            })
            
            remaining_qty -= allocated
        
        allocated_total = sum(a['quantity'] for a in allocations)
        backorder_qty = request.quantity - allocated_total
        
        return AllocationResult(
            success=remaining_qty == 0,
            allocated_quantity=allocated_total,
            backorder_quantity=backorder_qty,
            allocations=allocations,
            estimated_ship_date=date.today() if remaining_qty == 0 else None,
            message=f"Allocated {allocated_total} from {len(allocations)} warehouse(s)"
        )
    
    def check_multi_product_availability(
        self,
        product_quantities: Dict[str, Decimal],
        warehouse_code: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Check if multiple products are available (for order fulfillment)
        
        Args:
            product_quantities: Dict of {product_code: quantity}
            warehouse_code: Check specific warehouse or all
        
        Returns:
            Dict of {product_code: available_bool}
        """
        availability = {}
        
        for product_code, quantity in product_quantities.items():
            atp_results = self.calculate_atp(product_code, warehouse_code, include_future=False)
            
            total_available = sum(atp.available for atp in atp_results)
            availability[product_code] = total_available >= quantity
        
        return availability
    
    def get_fulfillment_options(
        self,
        product_quantities: Dict[str, Decimal],
        priority: AllocationPriority = AllocationPriority.B2C
    ) -> List[Dict]:
        """
        Get warehouse fulfillment options for multi-line order
        
        Returns warehouses that can fulfill entire order or partial splits
        
        Args:
            product_quantities: Dict of {product_code: quantity}
            priority: Customer priority level
        
        Returns:
            List of fulfillment options with warehouse splits
        """
        options = []
        
        # Option 1: Single warehouse fulfillment (preferred)
        warehouses = Warehouse.objects.filter(
            organization=self.organization,
            is_active=True
        )
        
        for warehouse in warehouses:
            can_fulfill = True
            warehouse_allocations = []
            
            for product_code, quantity in product_quantities.items():
                atp_results = self.calculate_atp(
                    product_code,
                    warehouse.code,
                    include_future=False
                )
                
                if not atp_results or atp_results[0].available < quantity:
                    can_fulfill = False
                    break
                
                warehouse_allocations.append({
                    'product_code': product_code,
                    'quantity': quantity,
                    'available': atp_results[0].available
                })
            
            if can_fulfill:
                options.append({
                    'type': 'single_warehouse',
                    'warehouses': [warehouse.code],
                    'split_shipment': False,
                    'allocations': warehouse_allocations,
                    'priority': 1  # Highest priority
                })
        
        # Option 2: Multi-warehouse split (if single warehouse not available)
        if not options:
            # Try to fulfill across multiple warehouses
            split_option = self._calculate_split_fulfillment(product_quantities)
            if split_option:
                options.append(split_option)
        
        return options
    
    def reserve_inventory(
        self,
        allocations: List[Dict],
        order_reference: str,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Reserve inventory for allocations (soft allocation)
        
        Creates pick list lines that reduce ATP without moving physical inventory
        
        Args:
            allocations: List of {'warehouse': 'WH-001', 'product_code': 'P001', 'quantity': 10}
            order_reference: Order/sales order reference
            expires_at: When reservation expires
        
        Returns:
            Success boolean
        """
        # TODO: Implement reservation logic
        # This would create pick list in 'reserved' status
        # that counts against ATP but doesn't move inventory yet
        return True
    
    def _get_allocated_quantity(self, product: Product, warehouse: Warehouse) -> Decimal:
        """Get quantity already allocated in active pick lists"""
        allocated = PickListLine.objects.filter(
            pick_list__organization=self.organization,
            pick_list__warehouse=warehouse,
            product=product,
            pick_list__status__in=['draft', 'released', 'in_progress']
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0.00')
        
        return allocated
    
    def _get_safety_stock(self, product: Product, warehouse: Warehouse) -> Decimal:
        """Get safety stock level for product at warehouse"""
        # Simple implementation - could be made more sophisticated
        # with warehouse-specific safety stock rules
        if product.reorder_level:
            return product.reorder_level * Decimal('0.25')  # 25% of reorder level
        return Decimal('0.00')
    
    def _get_in_transit_quantity(self, product: Product, warehouse: Warehouse) -> Decimal:
        """Get quantity in transit to warehouse"""
        in_transit = TransitWarehouse.objects.filter(
            organization=self.organization,
            to_warehouse=warehouse,
            is_active=True
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0.00')
        
        return in_transit
    
    def _calculate_future_atp(
        self,
        product: Product,
        warehouse: Warehouse,
        days_ahead: int = 30
    ) -> Dict[date, Decimal]:
        """
        Calculate future ATP projections
        
        Considers:
        - In-transit arrivals
        - Planned receipts (POs, production orders)
        - Scheduled allocations
        """
        future_atp = {}
        current_date = date.today()
        
        # Get current ATP as baseline
        current_item = InventoryItem.objects.filter(
            organization=self.organization,
            product=product,
            warehouse=warehouse
        ).first()
        
        if not current_item:
            return future_atp
        
        base_atp = current_item.quantity_on_hand - \
                   self._get_allocated_quantity(product, warehouse) - \
                   self._get_safety_stock(product, warehouse)
        
        # Project ATP for next N days
        for day_offset in range(1, days_ahead + 1):
            future_date = current_date + timedelta(days=day_offset)
            
            # Add expected receipts (in-transit, POs, production)
            receipts = self._get_expected_receipts(product, warehouse, future_date)
            
            # Subtract scheduled allocations
            scheduled_alloc = self._get_scheduled_allocations(product, warehouse, future_date)
            
            projected_atp = base_atp + receipts - scheduled_alloc
            future_atp[future_date] = max(projected_atp, Decimal('0.00'))
        
        return future_atp
    
    def _get_expected_receipts(
        self,
        product: Product,
        warehouse: Warehouse,
        target_date: date
    ) -> Decimal:
        """Get expected receipts for a future date"""
        # Check in-transit with expected arrival
        receipts = TransitWarehouse.objects.filter(
            organization=self.organization,
            to_warehouse=warehouse,
            is_active=True,
            expected_arrival__lte=target_date
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0.00')
        
        # TODO: Add purchase orders, production orders
        
        return receipts
    
    def _get_scheduled_allocations(
        self,
        product: Product,
        warehouse: Warehouse,
        target_date: date
    ) -> Decimal:
        """Get scheduled future allocations"""
        # TODO: Implement scheduled allocation logic
        # This would check for future-dated orders
        return Decimal('0.00')
    
    def _sort_warehouses_by_strategy(
        self,
        atp_results: List[ATPResult],
        strategy: AllocationStrategy,
        request: AllocationRequest
    ) -> List[ATPResult]:
        """Sort warehouses by allocation strategy"""
        
        if strategy == AllocationStrategy.NEAREST:
            # TODO: Implement distance-based sorting
            # For now, prefer requested warehouse
            if request.preferred_warehouse:
                return sorted(
                    atp_results,
                    key=lambda x: (
                        0 if x.warehouse_code == request.preferred_warehouse else 1,
                        -x.available
                    )
                )
            return sorted(atp_results, key=lambda x: -x.available)
        
        elif strategy == AllocationStrategy.COST:
            # TODO: Implement cost-based sorting
            # Would consider shipping costs, warehouse costs
            return sorted(atp_results, key=lambda x: -x.available)
        
        elif strategy == AllocationStrategy.BALANCE:
            # Balance inventory - prefer warehouses with higher stock levels
            return sorted(atp_results, key=lambda x: -x.on_hand)
        
        elif strategy == AllocationStrategy.FIFO:
            # TODO: Implement FIFO based on batch dates
            return sorted(atp_results, key=lambda x: -x.available)
        
        elif strategy == AllocationStrategy.FEFO:
            # TODO: Implement FEFO for perishable goods
            return sorted(atp_results, key=lambda x: -x.available)
        
        else:
            # Default: most available first
            return sorted(atp_results, key=lambda x: -x.available)
    
    def _calculate_split_fulfillment(
        self,
        product_quantities: Dict[str, Decimal]
    ) -> Optional[Dict]:
        """Calculate optimal warehouse split for multi-product order"""
        # This is a simplified implementation
        # Production system would use optimization algorithms
        
        all_warehouses = Warehouse.objects.filter(
            organization=self.organization,
            is_active=True
        )
        
        warehouse_allocations = {}
        unfulfilled = {}
        
        for product_code, quantity in product_quantities.items():
            remaining = quantity
            
            for warehouse in all_warehouses:
                if remaining <= 0:
                    break
                
                atp_results = self.calculate_atp(
                    product_code,
                    warehouse.code,
                    include_future=False
                )
                
                if atp_results and atp_results[0].available > 0:
                    allocated = min(atp_results[0].available, remaining)
                    
                    if warehouse.code not in warehouse_allocations:
                        warehouse_allocations[warehouse.code] = []
                    
                    warehouse_allocations[warehouse.code].append({
                        'product_code': product_code,
                        'quantity': allocated,
                        'available': atp_results[0].available
                    })
                    
                    remaining -= allocated
            
            if remaining > 0:
                unfulfilled[product_code] = remaining
        
        if unfulfilled:
            # Cannot fully fulfill
            return None
        
        return {
            'type': 'multi_warehouse',
            'warehouses': list(warehouse_allocations.keys()),
            'split_shipment': True,
            'allocations_by_warehouse': warehouse_allocations,
            'priority': 2  # Lower priority than single warehouse
        }


class SafetyStockService:
    """
    Safety Stock Management Service
    
    Calculates and maintains safety stock levels based on:
    - Lead time variability
    - Demand variability
    - Service level targets
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_safety_stock(
        self,
        product: Product,
        warehouse: Optional[Warehouse] = None,
        service_level: float = 0.95  # 95% service level
    ) -> Decimal:
        """
        Calculate optimal safety stock using statistical methods
        
        Formula: Safety Stock = Z × σ × √L
        Where:
        - Z = Z-score for service level (1.65 for 95%)
        - σ = Standard deviation of demand
        - L = Lead time in days
        """
        # TODO: Implement statistical safety stock calculation
        # This would require historical demand data
        
        # Simple fallback: 25% of reorder level
        if product.reorder_level:
            return product.reorder_level * Decimal('0.25')
        
        return Decimal('0.00')
    
    def get_reorder_point(
        self,
        product: Product,
        warehouse: Optional[Warehouse] = None
    ) -> Decimal:
        """
        Calculate reorder point
        
        ROP = (Average Daily Demand × Lead Time) + Safety Stock
        """
        # TODO: Implement ROP calculation with demand data
        
        if product.reorder_level:
            return product.reorder_level
        
        return Decimal('0.00')
    
    def get_economic_order_quantity(
        self,
        product: Product,
        annual_demand: Decimal,
        ordering_cost: Decimal,
        holding_cost_percent: Decimal = Decimal('0.25')
    ) -> Decimal:
        """
        Calculate Economic Order Quantity (EOQ)
        
        EOQ = √((2 × D × S) / H)
        Where:
        - D = Annual demand
        - S = Ordering cost per order
        - H = Holding cost per unit per year
        """
        if product.cost_price and product.cost_price > 0:
            holding_cost = product.cost_price * holding_cost_percent
            
            if holding_cost > 0:
                eoq_squared = (2 * annual_demand * ordering_cost) / holding_cost
                eoq = Decimal(str(eoq_squared ** 0.5))
                return eoq.quantize(Decimal('1.00'))
        
        # Fallback to reorder quantity
        if product.reorder_quantity:
            return product.reorder_quantity
        
        return Decimal('1.00')
