"""
Stock and Ledger Report Views
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from utils.calendars import (
    CalendarMode,
    ad_to_bs_string,
    bs_to_ad_string,
    maybe_coerce_bs_date,
)
from inventory.models import (
    InventoryItem,
    Product,
    Warehouse,
    StockLedger,
)


def _get_request_organization(request):
    """Helper to get organization from request."""
    return getattr(request, 'organization', None) or getattr(getattr(request, 'user', None), 'organization', None)


@login_required
def stock_report(request):
    """Display current stock levels across all warehouses."""
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view stock.')
        return redirect('dashboard')
    
    # Get filters
    selected_warehouse = request.GET.get('warehouse', '')
    selected_product = request.GET.get('product', '')
    
    # Build queryset
    stock_items = InventoryItem.objects.filter(
        organization=organization
    ).select_related(
        'product', 'warehouse', 'location', 'batch'
    ).annotate(
        total_value=F('quantity_on_hand') * F('unit_cost')
    ).order_by('product__code', 'warehouse__code')
    
    # Apply filters
    if selected_warehouse:
        stock_items = stock_items.filter(warehouse_id=selected_warehouse)
    if selected_product:
        stock_items = stock_items.filter(product_id=selected_product)
    
    # Get filter options
    warehouses = Warehouse.objects.filter(
        organization=organization, is_active=True
    ).order_by('name')
    
    products = Product.objects.filter(
        organization=organization, is_inventory_item=True
    ).order_by('name')
    
    context = {
        'organization': organization,
        'stock_items': stock_items,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': selected_warehouse,
        'selected_product': selected_product,
    }
    return render(request, 'inventory/stock_report.html', context)


@login_required
def ledger_report(request):
    """Display stock ledger movements with filtering."""
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view ledger.')
        return redirect('dashboard')

    calendar_mode = CalendarMode.normalize(
        getattr(organization, 'calendar_mode', CalendarMode.DEFAULT)
        if organization
        else CalendarMode.DEFAULT
    )

    def _coerce_date_value(ad_value: str, bs_value: str) -> str:
        ad_value = (ad_value or '').strip()
        bs_value = (bs_value or '').strip()
        if bs_value:
            converted = bs_to_ad_string(bs_value) or maybe_coerce_bs_date(bs_value)
            if converted:
                return converted if isinstance(converted, str) else converted.isoformat()
        if ad_value:
            parsed = parse_date(ad_value)
            if parsed:
                return parsed.isoformat()
        return ad_value

    # Get filters
    selected_warehouse = request.GET.get('warehouse', '')
    selected_product = request.GET.get('product', '')
    selected_txn_type = request.GET.get('txn_type', '')
    date_from_raw = request.GET.get('date_from', '')
    date_to_raw = request.GET.get('date_to', '')
    date_from_bs = request.GET.get('date_from_bs', '')
    date_to_bs = request.GET.get('date_to_bs', '')

    date_from = _coerce_date_value(date_from_raw, date_from_bs)
    date_to = _coerce_date_value(date_to_raw, date_to_bs)
    
    # Build queryset
    ledger_entries = StockLedger.objects.filter(
        organization=organization
    ).select_related(
        'product', 'warehouse', 'location', 'batch'
    ).order_by('-txn_date', '-id')
    
    # Apply filters
    if selected_warehouse:
        ledger_entries = ledger_entries.filter(warehouse_id=selected_warehouse)
    if selected_product:
        ledger_entries = ledger_entries.filter(product_id=selected_product)
    if selected_txn_type:
        ledger_entries = ledger_entries.filter(txn_type=selected_txn_type)
    if date_from:
        ledger_entries = ledger_entries.filter(txn_date__gte=date_from)
    if date_to:
        ledger_entries = ledger_entries.filter(txn_date__lte=date_to)
    
    # Limit to 100 for performance
    ledger_entries = ledger_entries[:100]
    
    # Get filter options
    warehouses = Warehouse.objects.filter(
        organization=organization, is_active=True
    ).order_by('name')
    
    products = Product.objects.filter(
        organization=organization, is_inventory_item=True
    ).order_by('name')
    
    txn_types = StockLedger.objects.filter(
        organization=organization
    ).values_list('txn_type', flat=True).distinct().order_by('txn_type')

    date_from_bs_display = date_from_bs or ad_to_bs_string(date_from) or ''
    date_to_bs_display = date_to_bs or ad_to_bs_string(date_to) or ''
    
    context = {
        'organization': organization,
        'ledger_entries': ledger_entries,
        'warehouses': warehouses,
        'products': products,
        'txn_types': txn_types,
        'selected_warehouse': selected_warehouse,
        'selected_product': selected_product,
        'selected_txn_type': selected_txn_type,
        'date_from': date_from,
        'date_from_bs': date_from_bs_display,
        'date_to': date_to,
        'date_to_bs': date_to_bs_display,
        'calendar_mode': calendar_mode,
    }
    return render(request, 'inventory/ledger_report.html', context)
