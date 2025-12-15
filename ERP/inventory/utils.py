"""
Inventory Utilities

Comprehensive inventory management utilities fully compatible with existing ERP models.
Includes product management, pricing, batch operations, stock tracking, and fulfillment.
"""

from typing import Optional, Dict, List, Any, Tuple, Union
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db import models, transaction
from django.db.models import Sum, Q, F, Case, When, Value, Count, Avg, Max, Min
from django.utils import timezone
from django.core.exceptions import ValidationError

from utils.organization import OrganizationService
from utils.cache_utils import cached_organization_data, CacheManager
from .models import (
    Product, Batch, Warehouse, Location, InventoryItem, StockLedger,
    ProductCategory, Unit, ProductUnit, PriceList, PriceListItem,
    CustomerPriceList, PromotionRule, PickList, PackingSlip, Shipment,
    Backorder, RMA
)


class ProductService:
    """
    Comprehensive product management service compatible with existing models.
    """

    @staticmethod
    def get_products_for_sale(organization: Any, category: Optional[Any] = None) -> models.QuerySet:
        """
        Get products available for sale.

        Args:
            organization: Organization instance
            category: Optional category filter

        Returns:
            QuerySet of saleable products
        """
        queryset = Product.objects.filter(
            organization=organization,
            is_active=True
        )

        if category:
            queryset = queryset.filter(category=category)

        return queryset.order_by('code')

    @staticmethod
    def search_products(
        organization: Any,
        query: str,
        limit: int = 50,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search products by code, name, or barcode.

        Args:
            organization: Organization instance
            query: Search query
            limit: Maximum results
            include_inactive: Include inactive products

        Returns:
            List of product dictionaries
        """
        if not query or len(query.strip()) < 2:
            return []

        search_query = query.strip()
        queryset = Product.objects.filter(
            Q(code__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(barcode__iexact=search_query) |
            Q(sku__iexact=search_query)
        )

        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        queryset = OrganizationService.filter_queryset_by_org(queryset, organization)
        products = queryset[:limit]

        # Get stock info for each product
        product_data = []
        for product in products:
            stock_info = ProductService.get_product_stock_info(product)
            product_data.append({
                'id': product.pk,
                'code': product.code,
                'name': product.name,
                'unit': ProductService.get_product_unit_display(product),
                'selling_price': str(product.sale_price),
                'available_stock': str(stock_info['available_stock']),
                'is_active': product.is_active,
                'category': product.category.name if product.category else '',
            })

        return product_data

    @staticmethod
    def get_product_unit_display(product: Product) -> str:
        """Get display unit for product."""
        if product.base_unit:
            return product.base_unit.name
        return "Unit"

    @staticmethod
    def get_product_stock_info(product: Product) -> Dict[str, Decimal]:
        """Get stock information for a product."""
        # Aggregate stock from InventoryItem
        stock_data = InventoryItem.objects.filter(
            organization=product.organization,
            product=product
        ).aggregate(
            total_on_hand=Sum('quantity_on_hand'),
            total_allocated=Sum('quantity_allocated'),
            total_available=Sum('quantity_available')
        )

        return {
            'total_on_hand': stock_data['total_on_hand'] or Decimal('0'),
            'total_allocated': stock_data['total_allocated'] or Decimal('0'),
            'available_stock': stock_data['total_available'] or Decimal('0'),
        }

    @staticmethod
    def get_product_with_rates(product_id: int, organization: Any) -> Optional[Dict[str, Any]]:
        """
        Get product with current pricing and stock information.

        Args:
            product_id: Product ID
            organization: Organization instance

        Returns:
            Product data dictionary or None
        """
        try:
            product = Product.objects.get(pk=product_id, organization=organization)

            # Get current pricing from PriceList
            pricing = ProductService.get_product_pricing(product)

            # Get stock information
            stock_info = ProductService.get_product_stock_info(product)

            # Check low stock
            is_low_stock = stock_info['total_on_hand'] <= (product.reorder_level or Decimal('0'))

            # Get available batches
            batches = Batch.objects.filter(
                organization=product.organization,
                product=product,
                is_active=True
            ).exclude(expiry_date__lt=timezone.localdate()).order_by('expiry_date')

            batch_info = []
            for batch in batches[:10]:  # Limit to first 10 batches
                # Get batch stock
                batch_stock = InventoryItem.objects.filter(
                    organization=product.organization,
                    product=product,
                    batch=batch
                ).aggregate(total=Sum('quantity_on_hand'))['total'] or Decimal('0')

                if batch_stock > 0:
                    batch_info.append({
                        'id': batch.pk,
                        'batch_number': batch.batch_number,
                        'serial_number': batch.serial_number,
                        'current_quantity': batch_stock,
                        'manufacture_date': batch.manufacture_date.isoformat() if batch.manufacture_date else None,
                        'expiry_date': batch.expiry_date.isoformat() if batch.expiry_date else None,
                        'days_to_expiry': (batch.expiry_date - timezone.localdate()).days if batch.expiry_date else None,
                    })

            return {
                'product': {
                    'id': product.pk,
                    'code': product.code,
                    'name': product.name,
                    'unit': ProductService.get_product_unit_display(product),
                    'description': product.description,
                    'category': product.category.name if product.category else '',
                    'base_unit': product.base_unit.name if product.base_unit else '',
                    'weight': str(product.weight) if product.weight else '',
                    'dimensions': f"{product.length or 0} x {product.width or 0} x {product.height or 0}",
                    'barcode': product.barcode,
                    'sku': product.sku,
                },
                'pricing': pricing,
                'stock': {
                    'total_on_hand': stock_info['total_on_hand'],
                    'total_allocated': stock_info['total_allocated'],
                    'available_stock': stock_info['available_stock'],
                    'is_low_stock': is_low_stock,
                    'reorder_level': product.reorder_level,
                },
                'batches': batch_info,
            }

        except Product.DoesNotExist:
            return None

    @staticmethod
    def get_product_pricing(product: Product) -> Dict[str, Any]:
        """Get current pricing for a product from PriceList."""
        pricing = {
            'default_selling': product.sale_price,
            'default_cost': product.cost_price,
            'currency': product.currency_code,
            'price_lists': []
        }

        # Get active price lists for this product
        price_lists = PriceList.objects.filter(
            organization=product.organization,
            is_active=True,
            valid_from__lte=timezone.now(),
            items__product=product
        ).distinct().prefetch_related('items')

        for price_list in price_lists:
            if price_list.valid_to and price_list.valid_to < timezone.now():
                continue

            price_item = price_list.items.filter(product=product).first()
            if price_item:
                pricing['price_lists'].append({
                    'list_name': price_list.name,
                    'list_code': price_list.code,
                    'unit_price': price_item.unit_price,
                    'min_quantity': price_item.min_quantity,
                    'discount_percent': price_item.discount_percent,
                    'currency': price_list.currency_code,
                })

        return pricing

    @staticmethod
    def check_stock_availability(
        organization: Any,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check stock availability for multiple items.

        Args:
            organization: Organization instance
            items: List of item dictionaries with 'product_id' and 'quantity'

        Returns:
            Availability check results
        """
        results = {
            'available': True,
            'items': [],
            'unavailable_items': []
        }

        for item in items:
            product_id = item.get('product_id')
            quantity = Decimal(str(item.get('quantity', 0)))

            try:
                product = Product.objects.get(pk=product_id, organization=organization)
                stock_info = ProductService.get_product_stock_info(product)

                available_qty = stock_info['available_stock']
                can_sell = available_qty >= quantity

                item_result = {
                    'product_id': product_id,
                    'product_code': product.code,
                    'product_name': product.name,
                    'requested_quantity': quantity,
                    'available_quantity': available_qty,
                    'can_sell': can_sell,
                }

                results['items'].append(item_result)

                if not can_sell:
                    results['available'] = False
                    results['unavailable_items'].append(item_result)

            except Product.DoesNotExist:
                item_result = {
                    'product_id': product_id,
                    'error': 'Product not found'
                }
                results['items'].append(item_result)
                results['available'] = False
                results['unavailable_items'].append(item_result)

        return results


class PricingService:
    """
    Advanced pricing and promotion management service.
    """

    @staticmethod
    def get_product_price(
        product: Product,
        customer_id: Optional[int] = None,
        quantity: Decimal = Decimal('1'),
        price_list_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get applicable price for a product based on customer, quantity, and price list.

        Args:
            product: Product instance
            customer_id: Customer ID for special pricing
            quantity: Order quantity
            price_list_code: Specific price list to use

        Returns:
            Price information dictionary
        """
        base_price = product.sale_price
        final_price = base_price
        applied_discounts = []
        price_source = 'default'

        # Check customer-specific pricing first
        if customer_id:
            customer_pricing = CustomerPriceList.objects.filter(
                organization=product.organization,
                customer_id=customer_id,
                is_active=True
            ).select_related('price_list').order_by('priority')

            for cust_price in customer_pricing:
                price_list = cust_price.price_list
                if price_list.is_active and PricingService._is_price_list_valid(price_list):
                    price_item = PriceListItem.objects.filter(
                        price_list=price_list,
                        product=product,
                        min_quantity__lte=quantity
                    ).order_by('-min_quantity').first()

                    if price_item:
                        final_price = price_item.unit_price
                        applied_discounts.append({
                            'type': 'customer_price_list',
                            'list_name': price_list.name,
                            'unit_price': price_item.unit_price,
                            'min_quantity': price_item.min_quantity,
                        })
                        price_source = f'customer_{price_list.code}'
                        break

        # Check specific price list if provided
        if price_list_code and price_source == 'default':
            try:
                price_list = PriceList.objects.get(
                    organization=product.organization,
                    code=price_list_code,
                    is_active=True
                )
                if PricingService._is_price_list_valid(price_list):
                    price_item = PriceListItem.objects.filter(
                        price_list=price_list,
                        product=product,
                        min_quantity__lte=quantity
                    ).order_by('-min_quantity').first()

                    if price_item:
                        final_price = price_item.unit_price
                        applied_discounts.append({
                            'type': 'price_list',
                            'list_name': price_list.name,
                            'unit_price': price_item.unit_price,
                            'min_quantity': price_item.min_quantity,
                        })
                        price_source = f'price_list_{price_list.code}'
            except PriceList.DoesNotExist:
                pass

        # Apply promotions
        promotions = PromotionRule.objects.filter(
            organization=product.organization,
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_to__gte=timezone.now(),
            apply_to_products=product
        )

        discount_amount = Decimal('0')
        for promo in promotions:
            if promo.is_valid():
                promo_discount = PricingService._calculate_promotion_discount(
                    promo, final_price, quantity
                )
                if promo_discount > discount_amount:
                    discount_amount = promo_discount
                    applied_discounts.append({
                        'type': 'promotion',
                        'promotion_name': promo.name,
                        'promotion_code': promo.code,
                        'discount_type': promo.promo_type,
                        'discount_value': promo.discount_value,
                        'discount_amount': promo_discount,
                    })

        final_price -= discount_amount

        return {
            'base_price': base_price,
            'final_price': max(final_price, Decimal('0')),  # Ensure non-negative
            'discount_amount': discount_amount,
            'price_source': price_source,
            'applied_discounts': applied_discounts,
            'currency': product.currency_code,
        }

    @staticmethod
    def _is_price_list_valid(price_list: PriceList) -> bool:
        """Check if price list is currently valid."""
        now = timezone.now()
        if price_list.valid_from and price_list.valid_from > now:
            return False
        if price_list.valid_to and price_list.valid_to < now:
            return False
        return True

    @staticmethod
    def _calculate_promotion_discount(promo: PromotionRule, price: Decimal, quantity: Decimal) -> Decimal:
        """Calculate discount amount for a promotion."""
        if promo.promo_type == 'percentage':
            return price * (promo.discount_value / Decimal('100'))
        elif promo.promo_type == 'fixed':
            return promo.discount_value
        elif promo.promo_type == 'bogo':
            # Buy one get one - simplified implementation
            free_items = quantity // 2
            return free_items * price
        elif promo.promo_type == 'volume':
            # Volume discount based on quantity
            if quantity >= promo.min_purchase_amount:
                return price * (promo.discount_value / Decimal('100'))
        return Decimal('0')


class BatchService:
    """
    Batch and lot management utilities compatible with existing Batch model.
    """

    @staticmethod
    def get_available_batches(
        product: Product,
        warehouse: Optional[Warehouse] = None,
        quantity: Optional[Decimal] = None,
        prefer_expiry_first: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get available batches for a product.

        Args:
            product: Product instance
            warehouse: Optional warehouse filter
            quantity: Required quantity (optional)
            prefer_expiry_first: Sort by expiry date first (FEFO)

        Returns:
            List of batch information dictionaries
        """
        queryset = InventoryItem.objects.filter(
            organization=product.organization,
            product=product,
            quantity_on_hand__gt=0
        ).exclude(
            batch__expiry_date__lt=timezone.localdate()
        ).select_related('batch', 'warehouse')

        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)

        # Sort by expiry date first (FEFO), then by batch creation
        if prefer_expiry_first:
            queryset = queryset.order_by('batch__expiry_date', 'batch__created_at')
        else:
            # FIFO: First in, first out
            queryset = queryset.order_by('batch__created_at')

        batch_data = []
        for item in queryset:
            if item.batch:
                batch_data.append({
                    'batch': item.batch,
                    'warehouse': item.warehouse,
                    'quantity_on_hand': item.quantity_on_hand,
                    'quantity_available': item.quantity_available,
                    'unit_cost': item.unit_cost,
                })

        if quantity:
            # Allocate from available batches
            return BatchService._allocate_from_batches(batch_data, quantity, prefer_expiry_first)

        return batch_data

    @staticmethod
    def _allocate_from_batches(batch_data: List[Dict], quantity: Decimal, fefo: bool) -> List[Dict]:
        """Allocate quantity from available batches."""
        allocations = []
        remaining_qty = quantity

        for batch_item in batch_data:
            if remaining_qty <= 0:
                break

            available_qty = min(batch_item['quantity_available'], remaining_qty)
            if available_qty > 0:
                allocation = batch_item.copy()
                allocation['allocated_quantity'] = available_qty
                allocations.append(allocation)
                remaining_qty -= available_qty

        return allocations

    @staticmethod
    def get_expiring_batches(organization: Any, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Get batches expiring within specified days.

        Args:
            organization: Organization instance
            days_ahead: Number of days to look ahead

        Returns:
            List of expiring batch information
        """
        cutoff_date = timezone.localdate() + timedelta(days=days_ahead)

        expiring_items = InventoryItem.objects.filter(
            organization=organization,
            batch__expiry_date__lte=cutoff_date,
            batch__expiry_date__gte=timezone.localdate(),
            quantity_on_hand__gt=0
        ).select_related('product', 'batch', 'warehouse').order_by('batch__expiry_date')

        return [{
            'batch_id': item.batch.pk,
            'batch_number': item.batch.batch_number,
            'serial_number': item.batch.serial_number,
            'product_code': item.product.code,
            'product_name': item.product.name,
            'warehouse_code': item.warehouse.code,
            'warehouse_name': item.warehouse.name,
            'expiry_date': item.batch.expiry_date.isoformat(),
            'days_to_expiry': (item.batch.expiry_date - timezone.localdate()).days,
            'quantity_on_hand': item.quantity_on_hand,
            'unit_cost': item.unit_cost,
        } for item in expiring_items]

    @staticmethod
    def get_expired_batches(organization: Any) -> List[Dict[str, Any]]:
        """
        Get expired batches with remaining stock.

        Args:
            organization: Organization instance

        Returns:
            List of expired batch information
        """
        expired_items = InventoryItem.objects.filter(
            organization=organization,
            batch__expiry_date__lt=timezone.localdate(),
            quantity_on_hand__gt=0
        ).select_related('product', 'batch', 'warehouse').order_by('batch__expiry_date')

        return [{
            'batch_id': item.batch.pk,
            'batch_number': item.batch.batch_number,
            'serial_number': item.batch.serial_number,
            'product_code': item.product.code,
            'product_name': item.product.name,
            'warehouse_code': item.warehouse.code,
            'warehouse_name': item.warehouse.name,
            'expiry_date': item.batch.expiry_date.isoformat(),
            'quantity_on_hand': item.quantity_on_hand,
            'unit_cost': item.unit_cost,
        } for item in expired_items]


class InventoryService:
    """
    Core inventory operations and calculations compatible with existing models.
    """

    @staticmethod
    @cached_organization_data(timeout=600)  # Cache for 10 minutes
    def get_inventory_summary(organization: Any) -> Dict[str, Any]:
        """
        Get comprehensive inventory summary.

        Args:
            organization: Organization instance

        Returns:
            Inventory summary data
        """
        # Get inventory products
        inventory_products = Product.objects.filter(
            organization=organization,
            is_inventory_item=True,
            is_active=True
        )

        # Aggregate stock data
        stock_summary = InventoryItem.objects.filter(
            organization=organization,
            product__is_inventory_item=True,
            product__is_active=True
        ).aggregate(
            total_products=Count('product', distinct=True),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
            total_items=Count('id'),
            total_on_hand=Sum('quantity_on_hand'),
            total_allocated=Sum('quantity_allocated'),
            total_available=Sum('quantity_available')
        )

        # Count low stock products
        low_stock_count = 0
        out_of_stock_count = 0

        for product in inventory_products:
            stock_info = ProductService.get_product_stock_info(product)
            if stock_info['total_on_hand'] == 0:
                out_of_stock_count += 1
            elif stock_info['total_on_hand'] <= (product.reorder_level or Decimal('0')):
                low_stock_count += 1

        # Get top moving products based on recent ledger activity
        start_date = timezone.now() - timedelta(days=30)
        top_products = StockLedger.objects.filter(
            organization=organization,
            txn_date__gte=start_date,
            txn_type='sale'
        ).values('product__code', 'product__name').annotate(
            total_sold=Sum('qty_out')
        ).order_by('-total_sold')[:10]

        return {
            'total_products': stock_summary['total_products'] or 0,
            'total_value': stock_summary['total_value'] or Decimal('0'),
            'total_items': stock_summary['total_items'] or 0,
            'total_on_hand': stock_summary['total_on_hand'] or Decimal('0'),
            'total_allocated': stock_summary['total_allocated'] or Decimal('0'),
            'total_available': stock_summary['total_available'] or Decimal('0'),
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
            'top_moving_products': list(top_products),
        }

    @staticmethod
    def get_stock_valuation(
        organization: Any,
        valuation_method: str = 'weighted_average',
        as_of_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Calculate inventory valuation using current stock levels.

        Args:
            organization: Organization instance
            valuation_method: Valuation method
            as_of_date: Date for valuation

        Returns:
            Valuation results
        """
        # Get current stock valuation
        valuation_data = InventoryItem.objects.filter(
            organization=organization,
            product__is_inventory_item=True,
            product__is_active=True,
            quantity_on_hand__gt=0
        ).select_related('product').values(
            'product__code', 'product__name', 'product__id'
        ).annotate(
            stock_quantity=Sum('quantity_on_hand'),
            total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
            average_cost=Avg('unit_cost')
        ).order_by('product__code')

        total_value = Decimal('0')
        product_valuations = []

        for item in valuation_data:
            total_value += item['total_value'] or Decimal('0')
            product_valuations.append({
                'product_id': item['product__id'],
                'product_code': item['product__code'],
                'product_name': item['product__name'],
                'stock_quantity': item['stock_quantity'],
                'average_cost': item['average_cost'],
                'total_value': item['total_value'],
            })

        return {
            'valuation_method': valuation_method,
            'total_value': total_value,
            'product_valuations': product_valuations,
            'as_of_date': as_of_date or timezone.localdate(),
        }

    @staticmethod
    def update_inventory_stock(
        organization: Any,
        product: Product,
        warehouse: Warehouse,
        location: Optional[Location],
        batch: Optional[Batch],
        quantity_change: Decimal,
        unit_cost: Optional[Decimal] = None,
        txn_type: str = 'adjustment',
        reference_id: str = '',
        notes: str = ''
    ) -> InventoryItem:
        """
        Update inventory stock levels and create ledger entry.

        Args:
            organization: Organization instance
            product: Product instance
            warehouse: Warehouse instance
            location: Location instance (optional)
            batch: Batch instance (optional)
            quantity_change: Positive for increase, negative for decrease
            unit_cost: Unit cost (optional)
            txn_type: Transaction type
            reference_id: Reference document ID
            notes: Transaction notes

        Returns:
            Updated InventoryItem instance
        """
        with transaction.atomic():
            # Get or create inventory item
            inventory_item, created = InventoryItem.objects.get_or_create(
                organization=organization,
                product=product,
                warehouse=warehouse,
                location=location,
                batch=batch,
                defaults={
                    'quantity_on_hand': Decimal('0'),
                    'quantity_allocated': Decimal('0'),
                    'quantity_available': Decimal('0'),
                    'unit_cost': unit_cost or Decimal('0'),
                    'total_cost': Decimal('0'),
                }
            )

            # Update quantities
            old_on_hand = inventory_item.quantity_on_hand
            inventory_item.quantity_on_hand += quantity_change

            # Update available quantity (on_hand - allocated)
            inventory_item.quantity_available = inventory_item.quantity_on_hand - inventory_item.quantity_allocated

            # Update cost if provided
            if unit_cost is not None:
                inventory_item.unit_cost = unit_cost
                inventory_item.total_cost = inventory_item.quantity_on_hand * unit_cost

            inventory_item.save()

            # Create stock ledger entry
            StockLedger.objects.create(
                organization=organization,
                product=product,
                warehouse=warehouse,
                location=location,
                batch=batch,
                txn_type=txn_type,
                reference_id=reference_id,
                txn_date=timezone.now(),
                qty_in=max(quantity_change, 0),
                qty_out=max(-quantity_change, 0),
                unit_cost=inventory_item.unit_cost,
                total_cost=abs(quantity_change) * inventory_item.unit_cost,
                created_at=timezone.now()
            )

            return inventory_item


class WarehouseService:
    """
    Multi-warehouse inventory management compatible with existing models.
    """

    @staticmethod
    def get_warehouse_stock_summary(organization: Any) -> List[Dict[str, Any]]:
        """
        Get stock summary by warehouse.

        Args:
            organization: Organization instance

        Returns:
            List of warehouse stock summaries
        """
        warehouses = Warehouse.objects.filter(
            organization=organization,
            is_active=True
        )

        summaries = []
        for warehouse in warehouses:
            # Aggregate stock data for warehouse
            stock_data = InventoryItem.objects.filter(
                organization=organization,
                warehouse=warehouse,
                quantity_on_hand__gt=0
            ).aggregate(
                total_products=Count('product', distinct=True),
                total_value=Sum(F('quantity_on_hand') * F('unit_cost')),
                total_items=Count('id'),
                total_on_hand=Sum('quantity_on_hand'),
                total_allocated=Sum('quantity_allocated'),
                total_available=Sum('quantity_available')
            )

            summaries.append({
                'warehouse_id': warehouse.pk,
                'warehouse_code': warehouse.code,
                'warehouse_name': warehouse.name,
                'total_products': stock_data['total_products'] or 0,
                'total_value': stock_data['total_value'] or Decimal('0'),
                'total_items': stock_data['total_items'] or 0,
                'total_on_hand': stock_data['total_on_hand'] or Decimal('0'),
                'total_allocated': stock_data['total_allocated'] or Decimal('0'),
                'total_available': stock_data['total_available'] or Decimal('0'),
                'address': f"{warehouse.address_line1}, {warehouse.city}, {warehouse.country_code}",
                'is_active': warehouse.is_active,
            })

        return summaries

    @staticmethod
    def transfer_stock(
        from_warehouse: Warehouse,
        to_warehouse: Warehouse,
        product: Product,
        quantity: Decimal,
        from_location: Optional[Location] = None,
        to_location: Optional[Location] = None,
        batch: Optional[Batch] = None,
        reference_id: str = '',
        user: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Transfer stock between warehouses.

        Args:
            from_warehouse: Source warehouse
            to_warehouse: Destination warehouse
            product: Product to transfer
            quantity: Quantity to transfer
            from_location: Source location
            to_location: Destination location
            batch: Batch to transfer
            reference_id: Reference document ID
            user: User performing transfer

        Returns:
            Tuple of (success, message)
        """
        if from_warehouse.organization != to_warehouse.organization:
            return False, "Cannot transfer between different organizations"

        # Check available stock
        available_stock = InventoryItem.objects.filter(
            organization=from_warehouse.organization,
            product=product,
            warehouse=from_warehouse,
            location=from_location,
            batch=batch
        ).aggregate(total=Sum('quantity_available'))['total'] or Decimal('0')

        if available_stock < quantity:
            return False, f"Insufficient stock in {from_warehouse.name}. Available: {available_stock}"

        with transaction.atomic():
            # Decrease from source
            InventoryService.update_inventory_stock(
                organization=from_warehouse.organization,
                product=product,
                warehouse=from_warehouse,
                location=from_location,
                batch=batch,
                quantity_change=-quantity,
                txn_type='transfer_out',
                reference_id=f"{reference_id}_out",
                notes=f"Transfer to {to_warehouse.code}"
            )

            # Increase at destination
            InventoryService.update_inventory_stock(
                organization=to_warehouse.organization,
                product=product,
                warehouse=to_warehouse,
                location=to_location,
                batch=batch,
                quantity_change=quantity,
                txn_type='transfer_in',
                reference_id=f"{reference_id}_in",
                notes=f"Transfer from {from_warehouse.code}"
            )

        return True, f"Successfully transferred {quantity} units from {from_warehouse.name} to {to_warehouse.name}"


class FulfillmentService:
    """
    Order fulfillment and logistics management service.
    """

    @staticmethod
    def create_pick_list(
        organization: Any,
        warehouse: Warehouse,
        order_reference: str,
        pick_items: List[Dict[str, Any]],
        priority: int = 5,
        user: Optional[Any] = None
    ) -> Tuple[bool, Union[PickList, str]]:
        """
        Create a pick list for order fulfillment.

        Args:
            organization: Organization instance
            warehouse: Warehouse for picking
            order_reference: Sales order reference
            pick_items: List of items to pick with product, quantity, location, batch
            priority: Picking priority (1-10)
            user: User creating the pick list

        Returns:
            Tuple of (success, pick_list_or_error_message)
        """
        try:
            with transaction.atomic():
                # Generate pick list number
                pick_number = f"PL-{timezone.now().strftime('%Y%m%d')}-{PickList.objects.filter(organization=organization).count() + 1:04d}"

                pick_list = PickList.objects.create(
                    organization=organization,
                    pick_number=pick_number,
                    warehouse=warehouse,
                    order_reference=order_reference,
                    status='draft',
                    priority=priority,
                    assigned_to=user.id if user else None,
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )

                # Create pick list lines
                line_number = 1
                for item in pick_items:
                    product = item['product']
                    quantity = item['quantity']
                    location = item.get('location')
                    batch = item.get('batch')

                    PickListLine.objects.create(
                        pick_list=pick_list,
                        product=product,
                        location=location,
                        batch=batch,
                        quantity_ordered=quantity,
                        quantity_picked=Decimal('0'),
                        line_number=line_number,
                        picked_by=None,
                        picked_at=None
                    )
                    line_number += 1

                return True, pick_list

        except Exception as e:
            return False, f"Failed to create pick list: {str(e)}"

    @staticmethod
    def update_pick_progress(
        pick_list: PickList,
        line_updates: List[Dict[str, Any]],
        user: Optional[Any] = None
    ) -> Tuple[bool, str]:
        """
        Update picking progress for pick list lines.

        Args:
            pick_list: PickList instance
            line_updates: List of line updates with line_number and quantity_picked
            user: User performing the picking

        Returns:
            Tuple of (success, message)
        """
        try:
            with transaction.atomic():
                total_lines = pick_list.lines.count()
                completed_lines = 0

                for update in line_updates:
                    line_number = update['line_number']
                    quantity_picked = update['quantity_picked']

                    line = PickListLine.objects.get(
                        pick_list=pick_list,
                        line_number=line_number
                    )

                    line.quantity_picked = quantity_picked
                    line.picked_by = user.id if user else None
                    line.picked_at = timezone.now()
                    line.save()

                    if line.quantity_picked >= line.quantity_ordered:
                        completed_lines += 1

                # Update pick list status
                if completed_lines == total_lines:
                    pick_list.status = 'picked'
                    pick_list.completed_date = timezone.now()
                elif pick_list.status == 'draft':
                    pick_list.status = 'picking'

                pick_list.updated_at = timezone.now()
                pick_list.save()

                return True, f"Pick list updated. {completed_lines}/{total_lines} lines completed."

        except Exception as e:
            return False, f"Failed to update pick progress: {str(e)}"

    @staticmethod
    def create_shipment(
        organization: Any,
        packing_slip: PackingSlip,
        carrier_name: str,
        tracking_number: str = '',
        shipping_cost: Decimal = Decimal('0'),
        estimated_delivery: Optional[date] = None,
        user: Optional[Any] = None
    ) -> Tuple[bool, Union[Shipment, str]]:
        """
        Create shipment for outbound delivery.

        Args:
            organization: Organization instance
            packing_slip: PackingSlip instance
            carrier_name: Shipping carrier name
            tracking_number: Tracking number
            shipping_cost: Shipping cost
            estimated_delivery: Estimated delivery date
            user: User creating shipment

        Returns:
            Tuple of (success, shipment_or_error_message)
        """
        try:
            with transaction.atomic():
                shipment_number = f"SH-{timezone.now().strftime('%Y%m%d')}-{Shipment.objects.filter(organization=organization).count() + 1:04d}"

                shipment = Shipment.objects.create(
                    organization=organization,
                    shipment_number=shipment_number,
                    packing_slip=packing_slip,
                    order_reference=packing_slip.order_reference,
                    carrier_name=carrier_name,
                    tracking_number=tracking_number,
                    service_type='',
                    status='pending',
                    ship_from_warehouse=packing_slip.warehouse,
                    ship_to_address='',  # Would come from order
                    estimated_delivery=estimated_delivery,
                    actual_delivery=None,
                    shipping_cost=shipping_cost,
                    notes='',
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )

                return True, shipment

        except Exception as e:
            return False, f"Failed to create shipment: {str(e)}"
