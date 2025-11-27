# Inventory/api/views.py
"""
REST API ViewSets for Inventory vertical features
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q
from drf_spectacular.utils import extend_schema, OpenApiTypes

from ..models import (
    Product, ProductCategory, Warehouse, Location, Batch,
    InventoryItem, StockLedger, PriceList, PriceListItem,
    CustomerPriceList, PromotionRule, TransitWarehouse,
    PickList, PickListLine, PackingSlip, Shipment,
    Backorder, RMA, RMALine
)
from .serializers import (
    ProductSerializer, ProductCategorySerializer, WarehouseSerializer,
    LocationSerializer, BatchSerializer, InventoryItemSerializer,
    StockLedgerSerializer, PriceListSerializer, PriceListItemSerializer,
    CustomerPriceListSerializer, PromotionRuleSerializer,
    TransitWarehouseSerializer, PickListSerializer, PickListLineSerializer,
    PackingSlipSerializer, ShipmentSerializer, BackorderSerializer,
    RMASerializer, RMALineSerializer
)
from api.permissions import IsOrganizationMember


class BaseInventoryViewSet(viewsets.ModelViewSet):
    """Base viewset with organization filtering"""
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user.organization)
    
    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class ProductCategoryViewSet(BaseInventoryViewSet):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'created_at']
    filterset_fields = ['is_active', 'parent']


class ProductViewSet(BaseInventoryViewSet):
    queryset = Product.objects.select_related('category', 'income_account', 'expense_account', 'inventory_account')
    serializer_class = ProductSerializer
    search_fields = ['code', 'name', 'barcode', 'sku']
    ordering_fields = ['code', 'name', 'sale_price', 'created_at']
    filterset_fields = ['category', 'is_inventory_item']
    
    @action(detail=True, methods=['get'])
    def inventory_status(self, request, pk=None):
        """Get inventory status across all warehouses"""
        product = self.get_object()
        items = InventoryItem.objects.filter(
            organization=request.user.organization,
            product=product
        ).select_related('warehouse', 'location', 'batch')
        
        total_qty = items.aggregate(total=Sum('quantity_on_hand'))['total'] or 0
        
        return Response({
            'product_code': product.code,
            'product_name': product.name,
            'total_on_hand': total_qty,
            'reorder_level': product.reorder_level,
            'needs_replenishment': total_qty < product.reorder_level if product.reorder_level else False,
            'warehouse_breakdown': InventoryItemSerializer(items, many=True).data
        })


class WarehouseViewSet(BaseInventoryViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    search_fields = ['code', 'name', 'city']
    ordering_fields = ['code', 'name']
    filterset_fields = ['is_active', 'country_code']


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related('warehouse')
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    search_fields = ['code', 'name']
    filterset_fields = ['warehouse', 'location_type', 'is_active']
    
    def get_queryset(self):
        return self.queryset.filter(warehouse__organization=self.request.user.organization)


class BatchViewSet(BaseInventoryViewSet):
    queryset = Batch.objects.select_related('product')
    serializer_class = BatchSerializer
    search_fields = ['batch_number', 'serial_number']
    filterset_fields = ['product']


class InventoryItemViewSet(BaseInventoryViewSet):
    queryset = InventoryItem.objects.select_related('product', 'warehouse', 'location', 'batch')
    serializer_class = InventoryItemSerializer
    filterset_fields = ['product', 'warehouse', 'location', 'batch']
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products below reorder level"""
        org = request.user.organization
        
        # Aggregate inventory by product
        from django.db.models import OuterRef, Subquery, DecimalField
        from django.db.models.functions import Coalesce
        
        products_with_reorder = Product.objects.filter(
            organization=org,
            is_inventory_item=True,
            reorder_level__isnull=False
        )
        
        low_stock_products = []
        for product in products_with_reorder:
            total_qty = InventoryItem.objects.filter(
                organization=org,
                product=product
            ).aggregate(total=Sum('quantity_on_hand'))['total'] or 0
            
            if total_qty < product.reorder_level:
                low_stock_products.append({
                    'product_id': product.id,
                    'product_code': product.code,
                    'product_name': product.name,
                    'current_stock': total_qty,
                    'reorder_level': product.reorder_level,
                    'shortage': product.reorder_level - total_qty
                })
        
        return Response(low_stock_products)


class StockLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to immutable stock ledger"""
    queryset = StockLedger.objects.select_related('product', 'warehouse', 'location', 'batch')
    serializer_class = StockLedgerSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filterset_fields = ['product', 'warehouse', 'txn_type']
    ordering_fields = ['txn_date', 'created_at']
    
    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user.organization)


# Pricing ViewSets
class PriceListViewSet(BaseInventoryViewSet):
    queryset = PriceList.objects.prefetch_related('items')
    serializer_class = PriceListSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active', 'currency_code']
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get all items in a price list"""
        price_list = self.get_object()
        items = price_list.items.select_related('product').all()
        return Response(PriceListItemSerializer(items, many=True).data)


class PriceListItemViewSet(viewsets.ModelViewSet):
    queryset = PriceListItem.objects.select_related('price_list', 'product')
    serializer_class = PriceListItemSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filterset_fields = ['price_list', 'product']
    
    def get_queryset(self):
        return self.queryset.filter(price_list__organization=self.request.user.organization)


class CustomerPriceListViewSet(BaseInventoryViewSet):
    queryset = CustomerPriceList.objects.select_related('price_list')
    serializer_class = CustomerPriceListSerializer
    filterset_fields = ['customer_id', 'price_list', 'is_active']
    
    @action(detail=False, methods=['get'])
    def by_customer(self, request):
        """Get price lists for a specific customer"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id parameter required'}, status=400)
        
        price_lists = self.get_queryset().filter(
            customer_id=customer_id,
            is_active=True
        ).order_by('priority')
        
        return Response(CustomerPriceListSerializer(price_lists, many=True).data)


class PromotionRuleViewSet(BaseInventoryViewSet):
    queryset = PromotionRule.objects.prefetch_related('apply_to_products')
    serializer_class = PromotionRuleSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active', 'promo_type']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active promotions"""
        from django.utils import timezone
        now = timezone.now()
        
        active_promos = self.get_queryset().filter(
            is_active=True,
            valid_from__lte=now,
            valid_to__gte=now
        )
        
        # Filter by max_uses if applicable
        valid_promos = [p for p in active_promos if p.is_valid()]
        
        return Response(PromotionRuleSerializer(valid_promos, many=True).data)


# Fulfillment ViewSets
class TransitWarehouseViewSet(BaseInventoryViewSet):
    queryset = TransitWarehouse.objects.select_related('from_warehouse', 'to_warehouse')
    serializer_class = TransitWarehouseSerializer
    search_fields = ['code', 'name', 'tracking_number']
    filterset_fields = ['is_active', 'from_warehouse', 'to_warehouse']


class PickListViewSet(BaseInventoryViewSet):
    queryset = PickList.objects.select_related('warehouse').prefetch_related('lines__product')
    serializer_class = PickListSerializer
    search_fields = ['pick_number', 'order_reference']
    filterset_fields = ['status', 'warehouse', 'priority']
    ordering_fields = ['pick_date', 'priority', 'created_at']
    
    @action(detail=True, methods=['post'])
    def release(self, request, pk=None):
        """Release pick list to warehouse"""
        pick_list = self.get_object()
        
        from ..services.fulfillment_service import PickPackShipService
        service = PickPackShipService(request.user.organization)
        
        try:
            service.release_pick_list(pick_list)
            return Response({'status': 'released'})
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
    
    @action(detail=True, methods=['post'])
    def record_pick(self, request, pk=None):
        """Record picked quantity for a line"""
        pick_list = self.get_object()
        line_number = request.data.get('line_number')
        quantity_picked = request.data.get('quantity_picked')
        picked_by = request.user.id
        
        from ..services.fulfillment_service import PickPackShipService
        service = PickPackShipService(request.user.organization)
        
        try:
            line = service.record_pick(pick_list, line_number, quantity_picked, picked_by)
            return Response(PickListLineSerializer(line).data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class PackingSlipViewSet(BaseInventoryViewSet):
    queryset = PackingSlip.objects.select_related('pick_list', 'warehouse')
    serializer_class = PackingSlipSerializer
    search_fields = ['packing_number', 'order_reference']
    filterset_fields = ['status', 'warehouse']


class ShipmentViewSet(BaseInventoryViewSet):
    queryset = Shipment.objects.select_related('packing_slip', 'ship_from_warehouse')
    serializer_class = ShipmentSerializer
    search_fields = ['shipment_number', 'tracking_number', 'order_reference']
    filterset_fields = ['status', 'carrier_name', 'ship_from_warehouse']
    ordering_fields = ['created_at', 'estimated_delivery']
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update shipment tracking status"""
        shipment = self.get_object()
        new_status = request.data.get('status')
        actual_delivery = request.data.get('actual_delivery')
        
        from ..services.fulfillment_service import PickPackShipService
        service = PickPackShipService(request.user.organization)
        
        try:
            shipment = service.update_shipment_status(shipment, new_status, actual_delivery)
            return Response(ShipmentSerializer(shipment).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)


class BackorderViewSet(BaseInventoryViewSet):
    queryset = Backorder.objects.select_related('product', 'warehouse')
    serializer_class = BackorderSerializer
    search_fields = ['backorder_number', 'order_reference']
    filterset_fields = ['is_fulfilled', 'product', 'warehouse', 'priority']
    ordering_fields = ['priority', 'expected_date', 'created_at']
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending backorders"""
        backorders = self.get_queryset().filter(is_fulfilled=False).order_by('priority', 'created_at')
        return Response(BackorderSerializer(backorders, many=True).data)


class RMAViewSet(BaseInventoryViewSet):
    queryset = RMA.objects.select_related('warehouse').prefetch_related('lines__product')
    serializer_class = RMASerializer
    search_fields = ['rma_number', 'original_order', 'original_invoice']
    filterset_fields = ['status', 'reason', 'customer_id']
    ordering_fields = ['requested_date', 'approved_date']
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve RMA"""
        rma = self.get_object()
        approved_by = request.user.id
        resolution = request.data.get('resolution')
        refund_amount = request.data.get('refund_amount')
        restocking_fee = request.data.get('restocking_fee', 0)
        
        from ..services.fulfillment_service import RMAService
        service = RMAService(request.user.organization)
        
        try:
            rma = service.approve_rma(rma, approved_by, resolution, refund_amount, restocking_fee)
            return Response(RMASerializer(rma).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)


# Allocation endpoints


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Calculate Available-to-Promise",
    description="Calculate ATP inventory for specified products"
)
def calculate_atp(request):
    """
    Calculate Available-to-Promise for products
    
    POST /api/inventory/allocation/atp/
    Body: {
        "product_codes": ["PROD001", "PROD002"],
        "warehouse_code": "WH-001" (optional),
        "include_future": true (optional)
    }
    """
    from ..services.allocation_service import AllocationService
    
    product_codes = request.data.get('product_codes', [])
    warehouse_code = request.data.get('warehouse_code')
    include_future = request.data.get('include_future', True)
    
    if not product_codes:
        return Response({'error': 'product_codes required'}, status=400)
    
    service = AllocationService(request.user.organization)
    results = {}
    
    for product_code in product_codes:
        atp_results = service.calculate_atp(
            product_code,
            warehouse_code,
            include_future
        )
        
        results[product_code] = [
            {
                'warehouse_code': atp.warehouse_code,
                'on_hand': float(atp.on_hand),
                'allocated': float(atp.allocated),
                'safety_stock': float(atp.safety_stock),
                'available': float(atp.available),
                'in_transit': float(atp.in_transit),
                'future_available': {
                    str(date): float(qty) 
                    for date, qty in atp.future_available.items()
                } if include_future else {}
            }
            for atp in atp_results
        ]
    
    return Response(results)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Allocate Inventory",
    description="Allocate inventory for an order with specified strategy"
)
def allocate_inventory(request):
    """
    Allocate inventory for an order
    
    POST /api/inventory/allocation/allocate/
    Body: {
        "product_code": "PROD001",
        "quantity": 10,
        "priority": "B2C",
        "customer_id": "CUST001" (optional),
        "preferred_warehouse": "WH-001" (optional),
        "strategy": "nearest" (optional: nearest, cost, balance, fifo, fefo)
    }
    """
    from ..services.allocation_service import (
        AllocationService, AllocationRequest,
        AllocationPriority, AllocationStrategy
    )
    from decimal import Decimal
    
    product_code = request.data.get('product_code')
    quantity = request.data.get('quantity')
    
    if not product_code or not quantity:
        return Response({'error': 'product_code and quantity required'}, status=400)
    
    # Parse priority
    priority_str = request.data.get('priority', 'B2C').upper()
    try:
        priority = AllocationPriority[priority_str]
    except KeyError:
        priority = AllocationPriority.B2C
    
    # Parse strategy
    strategy_str = request.data.get('strategy', 'nearest')
    try:
        strategy = AllocationStrategy(strategy_str)
    except ValueError:
        strategy = AllocationStrategy.NEAREST
    
    # Create allocation request
    alloc_request = AllocationRequest(
        product_code=product_code,
        quantity=Decimal(str(quantity)),
        priority=priority,
        customer_id=request.data.get('customer_id'),
        preferred_warehouse=request.data.get('preferred_warehouse')
    )
    
    service = AllocationService(request.user.organization)
    result = service.allocate_inventory(alloc_request, strategy)
    
    return Response({
        'success': result.success,
        'allocated_quantity': float(result.allocated_quantity),
        'backorder_quantity': float(result.backorder_quantity),
        'allocations': [
            {
                'warehouse': alloc['warehouse'],
                'quantity': float(alloc['quantity']),
                'location': alloc['location']
            }
            for alloc in result.allocations
        ],
        'estimated_ship_date': result.estimated_ship_date.isoformat() if result.estimated_ship_date else None,
        'message': result.message
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Check Order Availability",
    description="Check if multi-product order can be fulfilled"
)
def check_order_availability(request):
    """
    Check if multi-product order can be fulfilled
    
    POST /api/inventory/allocation/check-availability/
    Body: {
        "items": [
            {"product_code": "PROD001", "quantity": 10},
            {"product_code": "PROD002", "quantity": 5}
        ],
        "warehouse_code": "WH-001" (optional)
    }
    """
    from ..services.allocation_service import AllocationService
    from decimal import Decimal
    
    items = request.data.get('items', [])
    warehouse_code = request.data.get('warehouse_code')
    
    if not items:
        return Response({'error': 'items required'}, status=400)
    
    # Convert to dict
    product_quantities = {
        item['product_code']: Decimal(str(item['quantity']))
        for item in items
    }
    
    service = AllocationService(request.user.organization)
    availability = service.check_multi_product_availability(
        product_quantities,
        warehouse_code
    )
    
    all_available = all(availability.values())
    
    return Response({
        'can_fulfill': all_available,
        'availability': availability,
        'items': [
            {
                'product_code': code,
                'requested_quantity': float(product_quantities[code]),
                'available': avail
            }
            for code, avail in availability.items()
        ]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOrganizationMember])
@extend_schema(
    responses={200: OpenApiTypes.OBJECT},
    summary="Get Fulfillment Options",
    description="Get warehouse fulfillment options for order"
)
def get_fulfillment_options(request):
    """
    Get warehouse fulfillment options for order
    
    POST /api/inventory/allocation/fulfillment-options/
    Body: {
        "items": [
            {"product_code": "PROD001", "quantity": 10},
            {"product_code": "PROD002", "quantity": 5}
        ],
        "priority": "B2C" (optional)
    }
    """
    from ..services.allocation_service import AllocationService, AllocationPriority
    from decimal import Decimal
    
    items = request.data.get('items', [])
    
    if not items:
        return Response({'error': 'items required'}, status=400)
    
    # Parse priority
    priority_str = request.data.get('priority', 'B2C').upper()
    try:
        priority = AllocationPriority[priority_str]
    except KeyError:
        priority = AllocationPriority.B2C
    
    # Convert to dict
    product_quantities = {
        item['product_code']: Decimal(str(item['quantity']))
        for item in items
    }
    
    service = AllocationService(request.user.organization)
    options = service.get_fulfillment_options(product_quantities, priority)
    
    return Response({
        'options_count': len(options),
        'options': options
    })

