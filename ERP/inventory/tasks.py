# Inventory/tasks.py
"""
Celery tasks for inventory automation
Supports distributor and retailer vertical playbooks
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, F
from decimal import Decimal
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_low_stock_alerts():
    """
    Check for products below reorder level and send alerts
    Runs daily
    """
    from .models import Product, InventoryItem
    from usermanagement.models import Organization
    
    results = []
    
    for org in Organization.objects.filter(is_active=True):
        # Find products below reorder level
        low_stock_products = Product.objects.filter(
            organization=org,
            is_inventory_item=True,
            reorder_level__isnull=False
        )
        
        for product in low_stock_products:
            # Calculate total on-hand across all warehouses
            total_qty = InventoryItem.objects.filter(
                organization=org,
                product=product
            ).aggregate(
                total=Sum('quantity_on_hand')
            )['total'] or Decimal('0')
            
            if total_qty < product.reorder_level:
                results.append({
                    'org': org.name,
                    'product': product.code,
                    'current_qty': float(total_qty),
                    'reorder_level': float(product.reorder_level),
                    'shortage': float(product.reorder_level - total_qty)
                })
                
                logger.warning(
                    f"Low stock alert: {org.name} - {product.code} "
                    f"(Current: {total_qty}, Reorder: {product.reorder_level})"
                )
    
    return {
        'total_alerts': len(results),
        'alerts': results
    }


@shared_task
def generate_replenishment_suggestions():
    """
    Generate procurement suggestions based on reorder levels and lead times
    Runs daily
    """
from .models import Product, InventoryItem, Warehouse, ReorderRecommendation
    from usermanagement.models import Organization
    
    suggestions = []
    
    for org in Organization.objects.filter(is_active=True):
        products = Product.objects.filter(
            organization=org,
            is_inventory_item=True,
            reorder_level__isnull=False
        )
        
        ReorderRecommendation.objects.filter(organization=org).delete()
        warehouse_qs = Warehouse.objects.filter(organization=org, is_active=True)
        for product in products:
            for warehouse in warehouse_qs:
                # Get current stock at this warehouse
                wh_stock = InventoryItem.objects.filter(
                    organization=org,
                    product=product,
                    warehouse=warehouse
                ).aggregate(
                    total=Sum('quantity_on_hand')
                )['total'] or Decimal('0')
                
                # Check if below reorder level
                if wh_stock < product.reorder_level:
                    # Calculate suggested order quantity (2x reorder level - current stock)
                    suggested_qty = (product.reorder_level * 2) - wh_stock
                    
                    # Apply MOQ if specified
                    if product.min_order_quantity > suggested_qty:
                        suggested_qty = product.min_order_quantity
                    
                    suggestions.append({
                        'organization': org.name,
                        'product_code': product.code,
                        'product_name': product.name,
                        'warehouse_code': warehouse.code,
                        'current_stock': float(wh_stock),
                        'reorder_level': float(product.reorder_level),
                        'suggested_qty': float(suggested_qty),
                        'vendor_id': product.preferred_vendor_id,
                        'estimated_cost': float(suggested_qty * product.cost_price)
                    })
                    ReorderRecommendation.objects.create(
                        organization=org,
                        product=product,
                        warehouse=warehouse,
                        reorder_level=product.reorder_level,
                        current_stock=wh_stock,
                        shortage=product.reorder_level - wh_stock,
                        suggested_qty=suggested_qty,
                        estimated_cost=suggested_qty * product.cost_price,
                        vendor_id=product.preferred_vendor_id,
                    )
    
    logger.info(f"Generated {len(suggestions)} replenishment suggestions")
    return {
        'total_suggestions': len(suggestions),
        'suggestions': suggestions
    }


@shared_task
def process_backorder_fulfillment():
    """
    Check for backorders that can be fulfilled with available inventory
    Runs every 4 hours
    """
    from .models import Backorder, InventoryItem
    from .services.fulfillment_service import BackorderService
    
    fulfilled_count = 0
    partial_count = 0
    
    backorders = Backorder.objects.filter(
        is_fulfilled=False
    ).select_related('organization', 'product', 'warehouse')
    
    for backorder in backorders:
        service = BackorderService(backorder.organization)
        available_qty = service.check_backorder_fulfillment_availability(backorder)
        
        if available_qty > 0:
            try:
                # Fulfill what we can
                fulfill_qty = min(available_qty, backorder.quantity_remaining)
                backorder, is_fully_fulfilled = service.fulfill_backorder(backorder, fulfill_qty)
                
                if is_fully_fulfilled:
                    fulfilled_count += 1
                    logger.info(f"Fully fulfilled backorder {backorder.backorder_number}")
                else:
                    partial_count += 1
                    logger.info(
                        f"Partially fulfilled backorder {backorder.backorder_number}: "
                        f"{fulfill_qty} of {backorder.quantity_backordered}"
                    )
            except Exception as e:
                logger.error(f"Error fulfilling backorder {backorder.backorder_number}: {e}")
    
    return {
        'fully_fulfilled': fulfilled_count,
        'partially_fulfilled': partial_count
    }


@shared_task
def update_inventory_snapshots():
    """
    Recalculate inventory snapshots from ledger for accuracy verification
    Runs weekly
    """
    from .models import InventoryItem, StockLedger
    from django.db import transaction
    
    updated_count = 0
    
    inventory_items = InventoryItem.objects.select_related(
        'organization', 'product', 'warehouse'
    )
    
    for item in inventory_items:
        # Calculate from ledger
        ledger_balance = StockLedger.objects.filter(
            organization=item.organization,
            product=item.product,
            warehouse=item.warehouse,
            location=item.location,
            batch=item.batch
        ).aggregate(
            total_in=Sum('qty_in'),
            total_out=Sum('qty_out')
        )
        
        calculated_qty = (
            (ledger_balance['total_in'] or Decimal('0')) -
            (ledger_balance['total_out'] or Decimal('0'))
        )
        
        # Update if different
        if item.quantity_on_hand != calculated_qty:
            with transaction.atomic():
                item.quantity_on_hand = calculated_qty
                item.save()
                updated_count += 1
                logger.info(
                    f"Updated inventory snapshot: {item.organization.name} - "
                    f"{item.product.code} @ {item.warehouse.code}"
                )
    
    return {
        'items_updated': updated_count
    }


@shared_task
def apply_promotional_pricing():
    """
    Activate/deactivate promotional pricing based on date ranges
    Runs hourly
    """
    from .models import PromotionRule
    from django.utils import timezone
    
    now = timezone.now()
    activated = 0
    deactivated = 0
    
    # Activate promotions that should be active
    promotions_to_activate = PromotionRule.objects.filter(
        valid_from__lte=now,
        valid_to__gte=now,
        is_active=False
    )
    
    for promo in promotions_to_activate:
        if promo.max_uses is None or promo.current_uses < promo.max_uses:
            promo.is_active = True
            promo.save()
            activated += 1
    
    # Deactivate expired promotions
    promotions_to_deactivate = PromotionRule.objects.filter(
        valid_to__lt=now,
        is_active=True
    )
    
    deactivated = promotions_to_deactivate.update(is_active=False)
    
    return {
        'activated': activated,
        'deactivated': deactivated
    }
