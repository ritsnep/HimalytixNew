import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction, models
from django.contrib import messages
from django.urls import reverse
from accounting.models import SalesInvoice, SalesInvoiceLine, Customer, Currency
from inventory.models import Product
from usermanagement.models import Organization
from usermanagement.utils import PermissionUtils
from .models import Cart, CartItem, POSSettings


@login_required
def pos_home(request):
    """Main POS interface."""
    if not PermissionUtils.has_codename(request.user, request.organization, 'accounting_salesinvoice_add'):
        messages.error(request, "You don't have permission to access POS.")
        return redirect('dashboard')

    # Get or create active cart for user
    cart = Cart.objects.filter(
        user=request.user,
        organization=request.organization,
        status='active'
    ).first()

    if not cart:
        cart = Cart.objects.create(
            user=request.user,
            organization=request.organization,
            customer_name='Walk-in Customer'
        )

    # Get POS settings
    pos_settings, created = POSSettings.objects.get_or_create(
        organization=request.organization,
        defaults={
            'default_customer_name': 'Walk-in Customer',
            'enable_barcode_scanner': True,
            'auto_print_receipt': True,
        }
    )

    # Prepare cart data for JavaScript
    cart_data = {
        'id': cart.cart_id,
        'customer_name': cart.customer_name,
        'subtotal': float(cart.subtotal),
        'tax_total': float(cart.tax_total),
        'total': float(cart.total),
        'items': []
    }

    for item in cart.items.all():
        cart_data['items'].append({
            'id': item.cart_item_id,
            'product_name': item.product_name,
            'product_code': item.product_code,
            'quantity': float(item.quantity),
            'unit_price': float(item.unit_price),
            'line_total': float(item.line_total),
        })

    context = {
        'cart': cart,
        'cart_data_json': json.dumps(cart_data),
        'pos_settings': pos_settings,
        'page_title': 'Point of Sale',
    }

    return render(request, 'pos/pos.html', context)


@login_required
@require_POST
def add_to_cart(request):
    """Add item to cart via AJAX or HTMX."""
    try:
        if request.META.get('HTTP_HX_REQUEST'):
            # HTMX request - get data from POST
            product_code = request.POST.get('product_code', '').strip()
            quantity = Decimal(request.POST.get('quantity', 1))
        else:
            # JSON API request
            data = json.loads(request.body)
            product_code = data.get('product_code', '').strip()
            barcode = data.get('barcode', '').strip()
            quantity = Decimal(data.get('quantity', 1))

        if quantity <= 0:
            if request.META.get('HTTP_HX_REQUEST'):
                messages.error(request, 'Quantity must be positive')
                return redirect('pos:pos_home')
            return JsonResponse({'success': False, 'error': 'Quantity must be positive'})

        # Find product by code
        product = Product.objects.filter(
            organization=request.organization,
            code=product_code
        ).first()

        if not product:
            if request.META.get('HTTP_HX_REQUEST'):
                messages.error(request, 'Product not found')
                return redirect('pos:pos_home')
            return JsonResponse({'success': False, 'error': 'Product not found'})

        # Get or create active cart
        cart = Cart.objects.filter(
            user=request.user,
            organization=request.organization,
            status='active'
        ).first()

        if not cart:
            cart = Cart.objects.create(
                user=request.user,
                organization=request.organization,
                customer_name='Walk-in Customer'
            )

        # Check if item already in cart
        cart_item = CartItem.objects.filter(
            cart=cart,
            product=product
        ).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.save()
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                product_name=product.name,
                product_code=product.code,
                barcode=product.barcode,
                quantity=quantity,
                unit_price=product.sale_price,
            )

        # Recalculate cart totals
        cart.recalculate_totals()

        if request.META.get('HTTP_HX_REQUEST'):
            # Return HTML fragments for HTMX
            cart_items_html = render_cart_items(request, cart)
            cart_total_html = render_cart_total(request, cart)
            return HttpResponse(cart_items_html + cart_total_html)
        else:
            return JsonResponse({
                'success': True,
                'cart_total': float(cart.total),
                'item_count': cart.items.count()
            })

    except Exception as e:
        if request.META.get('HTTP_HX_REQUEST'):
            messages.error(request, f'Error adding product: {str(e)}')
            return redirect('pos:pos_home')
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def update_cart_item(request):
    """Update cart item quantity via AJAX or HTMX."""
    try:
        if request.META.get('HTTP_HX_REQUEST'):
            # HTMX request - get data from POST
            item_id = request.POST.get('item_id')
            quantity = Decimal(request.POST.get('quantity', 0))
        else:
            # JSON API request
            data = json.loads(request.body)
            item_id = data.get('item_id')
            quantity = Decimal(data.get('quantity', 0))

        if quantity < 0:
            if request.META.get('HTTP_HX_REQUEST'):
                messages.error(request, 'Quantity cannot be negative')
                return redirect('pos:pos_home')
            return JsonResponse({'success': False, 'error': 'Quantity cannot be negative'})

        cart_item = get_object_or_404(
            CartItem,
            cart_item_id=item_id,
            cart__user=request.user,
            cart__organization=request.organization,
            cart__status='active'
        )

        if quantity == 0:
            cart_item.delete()
        else:
            cart_item.quantity = quantity
            cart_item.save()

        # Recalculate cart totals
        cart_item.cart.recalculate_totals()

        if request.META.get('HTTP_HX_REQUEST'):
            # Return HTML fragments for HTMX
            cart_items_html = render_cart_items(request, cart_item.cart)
            cart_total_html = render_cart_total(request, cart_item.cart)
            return HttpResponse(cart_items_html + cart_total_html)
        else:
            return JsonResponse({
                'success': True,
                'cart_total': float(cart_item.cart.total),
                'item_count': cart_item.cart.items.count()
            })

    except Exception as e:
        if request.META.get('HTTP_HX_REQUEST'):
            messages.error(request, f'Error updating item: {str(e)}')
            return redirect('pos:pos_home')
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def remove_cart_item(request):
    """Remove item from cart via AJAX or HTMX."""
    try:
        if request.META.get('HTTP_HX_REQUEST'):
            # HTMX request - get data from POST
            item_id = request.POST.get('item_id')
        else:
            # JSON API request
            data = json.loads(request.body)
            item_id = data.get('item_id')

        cart_item = get_object_or_404(
            CartItem,
            cart_item_id=item_id,
            cart__user=request.user,
            cart__organization=request.organization,
            cart__status='active'
        )

        cart = cart_item.cart
        cart_item.delete()

        # Recalculate cart totals
        cart.recalculate_totals()

        if request.META.get('HTTP_HX_REQUEST'):
            # Return HTML fragments for HTMX
            cart_items_html = render_cart_items(request, cart)
            cart_total_html = render_cart_total(request, cart)
            return HttpResponse(cart_items_html + cart_total_html)
        else:
            return JsonResponse({
                'success': True,
                'cart_total': float(cart.total),
                'item_count': cart.items.count()
            })

    except Exception as e:
        if request.META.get('HTTP_HX_REQUEST'):
            messages.error(request, f'Error removing item: {str(e)}')
            return redirect('pos:pos_home')
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def clear_cart(request):
    """Clear all items from cart."""
    try:
        cart = Cart.objects.filter(
            user=request.user,
            organization=request.organization,
            status='active'
        ).first()

        if cart:
            cart.items.all().delete()
            cart.customer_name = 'Walk-in Customer'
            cart.recalculate_totals()
            cart.save()

        if request.META.get('HTTP_HX_REQUEST'):
            # Return HTML fragments for HTMX
            cart_items_html = render_cart_items(request, cart) if cart else '<div class="text-center text-muted py-4">No items in cart</div>'
            cart_total_html = render_cart_total(request, cart) if cart else '<div class="d-flex justify-content-between fw-bold fs-5"><span>Total:</span><span>$0.00</span></div>'
            return HttpResponse(cart_items_html + cart_total_html)
        else:
            return JsonResponse({'success': True})

    except Exception as e:
        if request.META.get('HTTP_HX_REQUEST'):
            messages.error(request, f'Error clearing cart: {str(e)}')
            return redirect('pos:pos_home')
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def checkout(request):
    """Process checkout and create sales invoice."""
    try:
        data = json.loads(request.body)
        payment_method = data.get('payment_method', 'cash')
        cash_received = Decimal(data.get('cash_received', 0))
        customer_name = data.get('customer_name', 'Walk-in Customer')

        cart = Cart.objects.filter(
            user=request.user,
            organization=request.organization,
            status='active'
        ).first()

        if not cart or not cart.items.exists():
            return JsonResponse({'success': False, 'error': 'Cart is empty'})

        if payment_method == 'cash' and cash_received < cart.total:
            return JsonResponse({'success': False, 'error': 'Insufficient cash received'})

        with transaction.atomic():
            # Get default customer or create walk-in customer
            customer = Customer.objects.filter(
                organization=request.organization,
                customer_name='Walk-in Customer'
            ).first()

            if not customer:
                customer = Customer.objects.create(
                    organization=request.organization,
                    customer_name='Walk-in Customer',
                    customer_type='individual',
                )

            # Get default currency
            currency = Currency.objects.filter(
                organization=request.organization,
                is_base_currency=True
            ).first()

            if not currency:
                currency = Currency.objects.filter(
                    organization=request.organization
                ).first()

            # Create sales invoice
            invoice = SalesInvoice.objects.create(
                organization=request.organization,
                customer=customer,
                customer_display_name=customer_name,
                invoice_date=timezone.now().date(),
                due_date=timezone.now().date(),  # Due immediately for POS
                currency=currency,
                subtotal=cart.subtotal,
                tax_total=cart.tax_total,
                total=cart.total,
                status='draft',
                created_by=request.user,
                notes=f'POS Transaction - {payment_method.capitalize()}',
            )

            # Create invoice lines
            line_number = 1
            for cart_item in cart.items.all():
                SalesInvoiceLine.objects.create(
                    invoice=invoice,
                    line_number=line_number,
                    description=cart_item.product_name,
                    product_code=cart_item.product_code,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.unit_price,
                    discount_amount=cart_item.discount_amount,
                    line_total=cart_item.line_total,
                    tax_amount=cart_item.tax_amount,
                    revenue_account=cart_item.product.income_account,
                )
                line_number += 1

            # Mark cart as completed
            cart.status = 'completed'
            cart.save()

            # Calculate change
            change = cash_received - cart.total if payment_method == 'cash' else Decimal(0)

            return JsonResponse({
                'success': True,
                'invoice_id': invoice.invoice_id,
                'invoice_number': invoice.invoice_number,
                'total': float(cart.total),
                'change': float(change),
                'print_url': reverse('accounting:sales_invoice_print', args=[invoice.invoice_id])
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def search_products(request):
    """Search products for POS lookup."""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))

    if len(query) < 2:
        if request.META.get('HTTP_HX_REQUEST'):
            return HttpResponse('<div class="text-center text-muted py-4">Type at least 2 characters to search</div>')
        return JsonResponse({'products': []})

    products = Product.objects.filter(
        organization=request.organization
    ).filter(
        models.Q(name__icontains=query) |
        models.Q(code__icontains=query) |
        models.Q(barcode__icontains=query)
    )[:limit]

    if request.META.get('HTTP_HX_REQUEST'):
        # Return HTML fragment for HTMX
        return render(request, 'pos/fragments/search_results.html', {
            'products': products
        })
    else:
        product_data = []
        for product in products:
            product_data.append({
                'id': product.id,
                'code': product.code,
                'name': product.name,
                'barcode': product.barcode,
                'sale_price': float(product.sale_price),
                'uom': product.uom,
            })

        return JsonResponse({'products': product_data})


@login_required
def top_products(request):
    """Return top products (for initial POS grid)"""
    limit = int(request.GET.get('limit', 20))
    products = Product.objects.filter(
        organization=request.organization
    ).order_by('name')[:limit]

    if request.META.get('HTTP_HX_REQUEST'):
        # Return HTML fragment for HTMX
        return render(request, 'pos/fragments/search_results.html', {
            'products': products
        })
    else:
        product_data = []
        for product in products:
            product_data.append({
                'id': product.id,
                'code': product.code,
                'name': product.name,
                'barcode': product.barcode,
                'sale_price': float(product.sale_price),
                'uom': product.uom,
            })

        return JsonResponse({'products': product_data})


@login_required
def get_cart(request):
    """Get current cart data."""
    cart = Cart.objects.filter(
        user=request.user,
        organization=request.organization,
        status='active'
    ).first()

    if not cart:
        return JsonResponse({'cart': None})

    items = []
    for item in cart.items.all():
        items.append({
            'id': item.cart_item_id,
            'product_code': item.product_code,
            'product_name': item.product_name,
            'quantity': float(item.quantity),
            'unit_price': float(item.unit_price),
            'line_total': float(item.line_total),
        })

    return JsonResponse({
        'cart': {
            'id': cart.cart_id,
            'customer_name': cart.customer_name,
            'subtotal': float(cart.subtotal),
            'tax_total': float(cart.tax_total),
            'total': float(cart.total),
            'items': items,
        }
    })


# HTMX Helper Functions
def render_cart_items(request, cart):
    """Render cart items HTML fragment for HTMX."""
    return render(request, 'pos/fragments/cart_items.html', {
        'cart': cart
    }).content.decode('utf-8')


def render_cart_total(request, cart):
    """Render cart total HTML fragment for HTMX."""
    return render(request, 'pos/fragments/cart_total.html', {
        'cart': cart
    }).content.decode('utf-8')
