"""
Purchase Invoice API Endpoints
Handles AJAX/JSON endpoints for purchase invoice operations
"""
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q, Sum

from accounting.models import Vendor, ChartOfAccount, APPayment
from inventory.models import Warehouse, Product, Unit


@login_required
@require_GET
def api_vendor_summary(request, vendor_id):
    """Get vendor summary with outstanding balance and terms"""
    try:
        vendor = Vendor.objects.get(id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({'error': 'Vendor not found'}, status=404)
    
    # Calculate outstanding balance from AP records
    outstanding_balance = Decimal('0.00')
    try:
        from accounting.models import PurchaseInvoice
        outstanding = PurchaseInvoice.objects.filter(
            vendor=vendor,
            is_posted=True,
            status='open'
        ).aggregate(total=Sum('grand_total'))
        outstanding_balance = outstanding.get('total') or Decimal('0.00')
    except Exception:
        pass
    
    # Get payment terms
    payment_term = vendor.payment_term.name if vendor.payment_term else 'Net'
    
    # Get last invoice date
    last_invoice_date = '-'
    try:
        from accounting.models import PurchaseInvoice
        last_inv = PurchaseInvoice.objects.filter(
            vendor=vendor
        ).order_by('-invoice_date').first()
        if last_inv:
            last_invoice_date = last_inv.invoice_date.strftime('%d %b %Y')
    except Exception:
        pass
    
    return JsonResponse({
        'outstanding_balance': str(outstanding_balance),
        'payment_terms': payment_term,
        'last_invoice_date': last_invoice_date,
        'status': 'Active' if vendor.is_active else 'Inactive',
    })


@login_required
@require_GET
def api_product_detail(request, product_id):
    """Get product details including unit information"""
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    
    unit_info = {}
    if product.base_unit:
        unit_info = {
            'unit_id': product.base_unit.id,
            'unit_code': product.base_unit.code,
            'unit_name': product.base_unit.name,
        }
    
    return JsonResponse({
        'id': product.id,
        'code': product.code,
        'name': product.name,
        'description': product.description or '',
        **unit_info,
    })


@login_required
@require_GET
def api_cash_bank_accounts(request):
    """Get list of cash and bank accounts for payment method selection"""
    organization = request.user.get_active_organization()
    
    # Get Cash and Bank accounts
    cash_bank_accounts = ChartOfAccount.objects.filter(
        organization=organization,
        account_type__in=['Cash', 'Bank'],
        is_active=True
    ).values('id', 'code', 'name')
    
    return JsonResponse({
        'accounts': list(cash_bank_accounts)
    })


@login_required
@require_GET
def api_warehouses(request):
    """Get list of active warehouses"""
    organization = request.user.get_active_organization()
    
    warehouses = Warehouse.objects.filter(
        organization=organization,
        is_active=True
    ).values('id', 'code', 'name')
    
    return JsonResponse({
        'warehouses': list(warehouses)
    })
