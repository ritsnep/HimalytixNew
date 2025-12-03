from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import StockReceiptForm, StockIssueForm
from .models import (
    Batch,
    InventoryItem,
    Product,
    ProductCategory,
    Warehouse,
    StockLedger,
)
from .services import InventoryService


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
    
    # Get filters
    selected_warehouse = request.GET.get('warehouse', '')
    selected_product = request.GET.get('product', '')
    selected_txn_type = request.GET.get('txn_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
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
        'date_to': date_to,
    }
    return render(request, 'inventory/ledger_report.html', context)


@login_required
def dashboard(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view inventory insights.')
        return redirect('dashboard')

    product_count = Product.objects.filter(organization=organization, is_inventory_item=True).count()
    warehouse_count = Warehouse.objects.filter(organization=organization).count()
    level_rows = (
        InventoryItem.objects.filter(
            organization=organization,
            product__reorder_level__isnull=False,
        )
        .values('product_id', 'product__reorder_level')
        .annotate(total_qty=Sum('quantity_on_hand'))
    )
    low_stock_count = sum(
        1 for row in level_rows if row['total_qty'] is not None and row['total_qty'] < row['product__reorder_level']
    )

    recent_movements = (
        StockLedger.objects.filter(organization=organization)
        .select_related('product', 'warehouse')
        .order_by('-txn_date')[:10]
    )

    context = {
        'organization': organization,
        'product_count': product_count,
        'warehouse_count': warehouse_count,
        'recent_movements': recent_movements,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'inventory/dashboard.html', context)


@login_required
def products(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing products.')
        return redirect('dashboard')

    products_qs = list(
        Product.objects.filter(organization=organization)
        .select_related('category')
        .order_by('name')
    )
    on_hand_map = {
        row['product_id']: row['total_qty']
        for row in InventoryItem.objects.filter(organization=organization)
        .values('product_id')
        .annotate(total_qty=Sum('quantity_on_hand'))
    }

    for product in products_qs:
        product.total_on_hand = on_hand_map.get(product.id, Decimal('0'))

    context = {
        'organization': organization,
        'products': products_qs,
    }
    return render(request, 'inventory/products.html', context)


@login_required
def categories(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing categories.')
        return redirect('dashboard')

    categories_qs = ProductCategory.objects.filter(organization=organization).order_by('name')
    context = {
        'organization': organization,
        'categories': categories_qs,
    }
    return render(request, 'inventory/categories.html', context)


@login_required
def warehouses(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before viewing warehouses.')
        return redirect('dashboard')

    warehouses_qs = list(
        Warehouse.objects.filter(organization=organization)
        .annotate(location_count=Count('locations'))
        .order_by('name')
    )
    warehouse_balances = {
        row['warehouse_id']: row['total_qty']
        for row in InventoryItem.objects.filter(organization=organization)
        .values('warehouse_id')
        .annotate(total_qty=Sum('quantity_on_hand'))
    }

    for warehouse in warehouses_qs:
        warehouse.total_on_hand = warehouse_balances.get(warehouse.id, Decimal('0'))

    context = {
        'organization': organization,
        'warehouses': warehouses_qs,
    }
    return render(request, 'inventory/warehouses.html', context)


@login_required
def stock_movements(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before reviewing stock movements.')
        return redirect('dashboard')

    recent_movements = (
        StockLedger.objects.filter(organization=organization)
        .select_related('product', 'warehouse', 'location')
        .order_by('-txn_date')[:20]
    )

    context = {
        'organization': organization,
        'recent_movements': recent_movements,
    }
    return render(request, 'inventory/stock_movements.html', context)


def _get_request_organization(request):
    return getattr(request, 'organization', None) or getattr(getattr(request, 'user', None), 'organization', None)


def _resolve_batch(organization, product, batch_number, serial_number):
    if not batch_number and not serial_number:
        return None
    batch_defaults = {
        'serial_number': serial_number or ''
    }
    batch, _ = Batch.objects.get_or_create(
        organization=organization,
        product=product,
        batch_number=batch_number or 'DEFAULT',
        defaults=batch_defaults
    )
    if serial_number and batch.serial_number != serial_number:
        batch.serial_number = serial_number
        batch.save(update_fields=['serial_number'])
    return batch


@login_required
def stock_receipt_create(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before recording a stock receipt.')
        return redirect('inventory:dashboard')

    form = StockReceiptForm(request.POST or None, organization=organization)
    if request.method == 'POST' and form.is_valid():
        cleaned = form.cleaned_data
        product = cleaned['product']
        warehouse = cleaned['warehouse']
        location = cleaned.get('location')
        batch = _resolve_batch(
            organization,
            product,
            cleaned.get('batch_number'),
            cleaned.get('serial_number')
        )

        try:
            InventoryService.create_stock_ledger_entry(
                organization=organization,
                product=product,
                warehouse=warehouse,
                location=location,
                batch=batch,
                txn_type='manual_receipt',
                reference_id=cleaned['reference_id'],
                qty_in=cleaned['quantity'],
                unit_cost=cleaned['unit_cost'],
                async_ledger=False,
            )
        except Exception as exc:  # pragma: no cover - defensive, surfaced via form errors
            form.add_error(None, f'Unable to record stock receipt: {exc}')
        else:
            messages.success(
                request,
                f"Added {cleaned['quantity']} {product.uom} of {product.name} to {warehouse.name}."
            )
            return redirect('inventory:stock_receipt_create')

    context = {
        'form': form,
        'page_title': 'Manual Stock Receipt',
        'card_title': 'Record Stock Receipt',
        'card_subtitle': 'Capture inventory received outside of purchasing documents.',
        'cancel_url': reverse('inventory:stock_movements'),
        'form_id': 'stock-receipt-form',
    }
    return render(request, 'Inventory/stock_transaction_form.html', context)


@login_required
def stock_issue_create(request):
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization before issuing stock.')
        return redirect('inventory:dashboard')

    form = StockIssueForm(request.POST or None, organization=organization)
    if request.method == 'POST' and form.is_valid():
        cleaned = form.cleaned_data
        product = cleaned['product']
        warehouse = cleaned['warehouse']
        location = cleaned.get('location')
        batch = _resolve_batch(
            organization,
            product,
            cleaned.get('batch_number'),
            cleaned.get('serial_number')
        )

        inventory_filter = {
            'organization': organization,
            'product': product,
            'warehouse': warehouse,
            'location': location,
            'batch': batch,
        }
        try:
            inventory_item = InventoryItem.objects.get(**inventory_filter)
        except InventoryItem.DoesNotExist:
            form.add_error(None, 'No on-hand inventory found for the selected product, warehouse, location, and batch.')
        else:
            qty = cleaned['quantity']
            if inventory_item.quantity_on_hand < qty:
                form.add_error('quantity', f'Only {inventory_item.quantity_on_hand} available for issue.')
            else:
                reference = cleaned['reference_id']
                reason = cleaned.get('reason')
                if reason:
                    reference = (f'{reference} | {reason}' if reference else reason)[:100]
                try:
                    InventoryService.create_stock_ledger_entry(
                        organization=organization,
                        product=product,
                        warehouse=warehouse,
                        location=location,
                        batch=batch,
                        txn_type='manual_issue',
                        reference_id=reference,
                        qty_out=qty,
                        unit_cost=inventory_item.unit_cost,
                        async_ledger=False,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    form.add_error(None, f'Unable to record stock issue: {exc}')
                else:
                    messages.success(
                        request,
                        f"Issued {qty} {product.uom} of {product.name} from {warehouse.name}."
                    )
                    return redirect('inventory:stock_issue_create')

    context = {
        'form': form,
        'page_title': 'Manual Stock Issue',
        'card_title': 'Record Stock Issue',
        'card_subtitle': 'Remove inventory for adjustments, samples, or other manual reasons.',
        'cancel_url': reverse('inventory:stock_movements'),
        'form_id': 'stock-issue-form',
    }
    return render(request, 'Inventory/stock_transaction_form.html', context)


@login_required
def stock_report(request):
    \"\"\"Display current stock levels across all warehouses.\"\"\"
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view stock.')
        return redirect('dashboard')

    # Get filter parameters
    warehouse_id = request.GET.get('warehouse')
    product_id = request.GET.get('product')
    
    # Base queryset
    stock_items = InventoryItem.objects.filter(
        organization=organization
    ).select_related(
        'product', 'warehouse', 'location', 'batch'
    ).order_by('product__code', 'warehouse__code')

    # Apply filters
    if warehouse_id:
        stock_items = stock_items.filter(warehouse_id=warehouse_id)
    if product_id:
        stock_items = stock_items.filter(product_id=product_id)

    # Calculate total value
    from django.db.models import DecimalField, ExpressionWrapper, F
    stock_items = stock_items.annotate(
        total_value=ExpressionWrapper(
            F('quantity_on_hand') * F('unit_cost'),
            output_field=DecimalField(max_digits=24, decimal_places=4)
        )
    )

    # Get warehouses and products for filter dropdowns
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
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
    }
    return render(request, 'inventory/stock_report.html', context)


@login_required
def ledger_report(request):
    \"\"\"Display stock movement history with filters.\"\"\"
    organization = _get_request_organization(request)
    if organization is None:
        messages.error(request, 'Select an organization to view ledger.')
        return redirect('dashboard')

    # Get filter parameters
    warehouse_id = request.GET.get('warehouse')
    product_id = request.GET.get('product')
    txn_type = request.GET.get('txn_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset
    ledger_entries = StockLedger.objects.filter(
        organization=organization
    ).select_related(
        'product', 'warehouse', 'location', 'batch'
    ).order_by('-txn_date', '-id')

    # Apply filters
    if warehouse_id:
        ledger_entries = ledger_entries.filter(warehouse_id=warehouse_id)
    if product_id:
        ledger_entries = ledger_entries.filter(product_id=product_id)
    if txn_type:
        ledger_entries = ledger_entries.filter(txn_type=txn_type)
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            ledger_entries = ledger_entries.filter(txn_date__gte=date_from_obj)
        except ValueError:
            messages.warning(request, 'Invalid date format for start date.')
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            ledger_entries = ledger_entries.filter(txn_date__lte=date_to_obj)
        except ValueError:
            messages.warning(request, 'Invalid date format for end date.')

    # Limit to recent 100 entries for performance
    ledger_entries = ledger_entries[:100]

    # Get filter options
    warehouses = Warehouse.objects.filter(
        organization=organization, is_active=True
    ).order_by('name')
    
    products = Product.objects.filter(
        organization=organization, is_inventory_item=True
    ).order_by('name')

    # Transaction types
    txn_types = StockLedger.objects.filter(
        organization=organization
    ).values_list('txn_type', flat=True).distinct()

    context = {
        'organization': organization,
        'ledger_entries': ledger_entries,
        'warehouses': warehouses,
        'products': products,
        'txn_types': sorted(txn_types),
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
        'selected_txn_type': txn_type,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'inventory/ledger_report.html', context)
