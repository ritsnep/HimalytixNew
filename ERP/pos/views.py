import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, QueryDict
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from django.db import transaction, models
from django.contrib import messages
from django.urls import reverse
from accounting.models import SalesInvoice, SalesInvoiceLine, Customer, Currency
from inventory.models import Product
from usermanagement.models import Organization
from usermanagement.utils import PermissionUtils
from .models import Cart, CartItem, POSSettings


def _is_htmx(request):
    return bool(request.META.get('HTTP_HX_REQUEST'))


def _hx_trigger(response, message, level='success'):
    """Attach HX-Trigger header to surface toast messages on the client."""
    response['HX-Trigger'] = json.dumps({
        'showMessage': {
            'message': message,
            'type': level
        }
    })
    return response


def _get_payload(request):
    """Extract payload from HTMX form posts or JSON API calls."""
    if _is_htmx(request):
        return request.POST
    try:
        if request.body:
            return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        try:
            # Fallback for incorrectly labeled form posts (urlencoded)
            parsed = QueryDict(request.body.decode('utf-8'))
            return parsed
        except Exception:
            return {}
    return {}


def _get_or_create_active_cart(request, customer_name=None):
    """Return the user's active cart or create one with sane defaults."""
    settings_obj, _ = POSSettings.objects.get_or_create(
        organization=request.organization,
        defaults={
            'default_customer_name': 'Walk-in Customer',
            'enable_barcode_scanner': True,
            'auto_print_receipt': True,
        }
    )

    cart = Cart.objects.filter(
        user=request.user,
        organization=request.organization,
        status='active'
    ).first()

    if not cart:
        cart = Cart.objects.create(
            user=request.user,
            organization=request.organization,
            customer_name=customer_name or settings_obj.default_customer_name or 'Walk-in Customer'
        )

    return cart, settings_obj


def _create_fresh_cart(request, customer_name=None):
    """Create a brand new active cart for the user."""
    settings_obj, _ = POSSettings.objects.get_or_create(
        organization=request.organization,
        defaults={
            'default_customer_name': 'Walk-in Customer',
            'enable_barcode_scanner': True,
            'auto_print_receipt': True,
        }
    )
    return Cart.objects.create(
        user=request.user,
        organization=request.organization,
        customer_name=customer_name or settings_obj.default_customer_name or 'Walk-in Customer'
    )


def _render_cart_fragments(request, cart):
    """Return combined HTML fragments for cart items and totals."""
    cart_items_html = render_cart_items(request, cart)
    cart_total_html = render_cart_total(request, cart)
    return cart_items_html + cart_total_html


@login_required
@ensure_csrf_cookie
def pos_home(request):
    """Main POS interface."""
    if not PermissionUtils.has_codename(request.user, request.organization, 'accounting_salesinvoice_add'):
        messages.error(request, "You don't have permission to access POS.")
        return redirect('dashboard')

    cart, pos_settings = _get_or_create_active_cart(request)

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
        data = _get_payload(request)
        product_code = (data.get('product_code') or data.get('code') or '').strip()
        barcode = (data.get('barcode') or '').strip()
        try:
            quantity = Decimal(data.get('quantity', 1))
        except (InvalidOperation, TypeError):
            quantity = Decimal(0)

        if quantity <= 0:
            msg = 'Quantity must be positive'
            if _is_htmx(request):
                resp = HttpResponse(render_cart_items(request, None))
                return _hx_trigger(resp, msg, 'error')
            return JsonResponse({'success': False, 'error': msg}, status=400)

        # Find product by code or barcode
        product = Product.objects.filter(
            organization=request.organization
        ).filter(
            models.Q(code=product_code) |
            models.Q(barcode=barcode) |
            models.Q(barcode=product_code)
        ).first()

        if not product:
            msg = 'Product not found'
            if _is_htmx(request):
                resp = HttpResponse(render_cart_items(request, None))
                return _hx_trigger(resp, msg, 'error')
            return JsonResponse({'success': False, 'error': msg}, status=404)

        cart, _settings = _get_or_create_active_cart(request)

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

        if _is_htmx(request):
            fragments = _render_cart_fragments(request, cart)
            resp = HttpResponse(fragments)
            return _hx_trigger(resp, 'Product added to cart')

        return JsonResponse({
            'success': True,
            'cart_total': float(cart.total),
            'item_count': cart.items.count()
        })

    except Exception as e:
        if _is_htmx(request):
            resp = HttpResponse(render_cart_items(request, None))
            return _hx_trigger(resp, f'Error adding product: {str(e)}', 'error')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def update_cart_item(request):
    """Update cart item quantity via AJAX or HTMX."""
    try:
        data = _get_payload(request)
        item_id = data.get('item_id')
        try:
            quantity = Decimal(data.get('quantity', 0))
        except (InvalidOperation, TypeError):
            quantity = Decimal(-1)

        if quantity < 0:
            msg = 'Quantity cannot be negative'
            if _is_htmx(request):
                resp = HttpResponse(render_cart_items(request, None))
                return _hx_trigger(resp, msg, 'error')
            return JsonResponse({'success': False, 'error': msg}, status=400)

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

        if _is_htmx(request):
            fragments = _render_cart_fragments(request, cart_item.cart)
            resp = HttpResponse(fragments)
            return _hx_trigger(resp, 'Cart updated')

        return JsonResponse({
            'success': True,
            'cart_total': float(cart_item.cart.total),
            'item_count': cart_item.cart.items.count()
        })

    except Exception as e:
        if _is_htmx(request):
            resp = HttpResponse(render_cart_items(request, None))
            return _hx_trigger(resp, f'Error updating item: {str(e)}', 'error')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def remove_cart_item(request):
    """Remove item from cart via AJAX or HTMX."""
    try:
        data = _get_payload(request)
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

        if _is_htmx(request):
            fragments = _render_cart_fragments(request, cart)
            resp = HttpResponse(fragments)
            return _hx_trigger(resp, 'Item removed')

        return JsonResponse({
            'success': True,
            'cart_total': float(cart.total),
            'item_count': cart.items.count()
        })

    except Exception as e:
        if _is_htmx(request):
            resp = HttpResponse(render_cart_items(request, None))
            return _hx_trigger(resp, f'Error removing item: {str(e)}', 'error')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def clear_cart(request):
    """Clear all items from cart."""
    try:
        cart, _settings = _get_or_create_active_cart(request)

        cart.items.all().delete()
        cart.customer_name = _settings.default_customer_name or 'Walk-in Customer'
        cart.recalculate_totals()
        cart.save(update_fields=['customer_name'])

        if _is_htmx(request):
            fragments = _render_cart_fragments(request, cart)
            receipt_reset = '<div id="receipt-actions" hx-swap-oob="true" style="display:none;"></div>'
            resp = HttpResponse(fragments + receipt_reset)
            return _hx_trigger(resp, 'Cart cleared')

        return JsonResponse({'success': True})

    except Exception as e:
        if _is_htmx(request):
            resp = HttpResponse(render_cart_items(request, None))
            return _hx_trigger(resp, f'Error clearing cart: {str(e)}', 'error')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def checkout(request):
    """Process checkout and create sales invoice."""
    try:
        data = _get_payload(request)
        payment_method = data.get('payment_method', 'cash')
        try:
            cash_received = Decimal(data.get('cash_received', 0))
        except (InvalidOperation, TypeError):
            cash_received = Decimal(0)
        customer_name = data.get('customer_name') or 'Walk-in Customer'

        cart, _settings = _get_or_create_active_cart(request, customer_name=customer_name)

        if not cart or not cart.items.exists():
            msg = 'Cart is empty'
            if _is_htmx(request):
                resp = HttpResponse(render_cart_items(request, cart))
                return _hx_trigger(resp, msg, 'error')
            return JsonResponse({'success': False, 'error': msg}, status=400)

        if payment_method == 'cash' and cash_received < cart.total:
            msg = 'Insufficient cash received'
            if _is_htmx(request):
                resp = HttpResponse(render_cart_items(request, cart))
                return _hx_trigger(resp, msg, 'error')
            return JsonResponse({'success': False, 'error': msg}, status=400)

        with transaction.atomic():
            # Get default customer or create walk-in customer
            customer = Customer.objects.filter(
                organization=request.organization,
                display_name='Walk-in Customer'
            ).first()

            if not customer:
                customer = Customer.objects.create(
                    organization=request.organization,
                    display_name='Walk-in Customer',
                    legal_name='Walk-in Customer',
                    status='active'
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

            if _is_htmx(request):
                # Prepare fresh cart for next sale
                new_cart, _ = _get_or_create_active_cart(request)
                new_cart.items.all().delete()
                new_cart.recalculate_totals()

                fragments = _render_cart_fragments(request, new_cart)
                receipt_html = render(request, 'pos/fragments/receipt_actions.html', {
                    'invoice': invoice,
                    'change': change
                }).content.decode('utf-8')
                response = HttpResponse(fragments + receipt_html)
                response['HX-Trigger'] = json.dumps({
                    'showMessage': {'message': 'Sale completed', 'type': 'success'}
                })
                return response

            return JsonResponse({
                'success': True,
                'invoice_id': invoice.invoice_id,
                'invoice_number': invoice.invoice_number,
                'total': float(cart.total),
                'change': float(change),
                'print_url': reverse('accounting:sales_invoice_print', args=[invoice.invoice_id])
            })

    except Exception as e:
        if _is_htmx(request):
            resp = HttpResponse(render_cart_items(request, None))
            return _hx_trigger(resp, f'Checkout failed: {str(e)}', 'error')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def search_products(request):
    """Search products for POS lookup."""
    query = request.GET.get('search_query') or request.GET.get('q') or ''
    query = query.strip()
    try:
        limit = int(request.GET.get('limit', 10))
    except (ValueError, TypeError):
        limit = 10

    if len(query) < 2:
        if _is_htmx(request):
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
            'products': products,
            'heading': 'Search Results'
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
    try:
        limit = int(request.GET.get('limit', 20))
    except (ValueError, TypeError):
        limit = 20
    products = Product.objects.filter(
        organization=request.organization
    ).order_by('name')[:limit]

    if request.META.get('HTTP_HX_REQUEST'):
        # Return HTML fragment for HTMX
        return render(request, 'pos/fragments/search_results.html', {
            'products': products,
            'heading': 'Popular Products'
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
    cart, _settings = _get_or_create_active_cart(request)

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


@login_required
@require_POST
def hold_cart(request):
    """Place the current active cart on hold and start a fresh cart."""
    cart, _settings = _get_or_create_active_cart(request)
    if not cart or not cart.items.exists():
        msg = 'Nothing to hold'
        if _is_htmx(request):
            resp = HttpResponse(_render_cart_fragments(request, cart))
            return _hx_trigger(resp, msg, 'error')
        return JsonResponse({'success': False, 'error': msg}, status=400)

    cart.status = 'held'
    cart.save(update_fields=['status', 'updated_at'])

    new_cart = _create_fresh_cart(request)
    fragments = _render_cart_fragments(request, new_cart)
    held_fragment = render_held_orders(request)

    if _is_htmx(request):
        resp = HttpResponse(fragments + held_fragment)
        return _hx_trigger(resp, 'Order held')

    return JsonResponse({'success': True})


@login_required
def list_held_carts(request):
    """Return held carts fragment."""
    html = render_held_orders(request)
    if _is_htmx(request):
        return HttpResponse(html)
    return JsonResponse({'html': html})


@login_required
@require_POST
def resume_cart(request):
    """Resume a held cart as the active one."""
    data = _get_payload(request)
    cart_id = data.get('cart_id')
    held_cart = get_object_or_404(
        Cart,
        cart_id=cart_id,
        user=request.user,
        organization=request.organization,
        status='held'
    )

    Cart.objects.filter(
        user=request.user,
        organization=request.organization,
        status='active'
    ).update(status='cancelled')

    held_cart.status = 'active'
    held_cart.save(update_fields=['status', 'updated_at'])

    fragments = _render_cart_fragments(request, held_cart)
    held_fragment = render_held_orders(request)

    if _is_htmx(request):
        resp = HttpResponse(fragments + held_fragment)
        return _hx_trigger(resp, 'Order resumed')

    return JsonResponse({'success': True})


@login_required
@require_POST
def update_cart_meta(request):
    """Update customer name and notes on the active cart."""
    cart, _settings = _get_or_create_active_cart(request)
    if not cart:
        return JsonResponse({'success': False, 'error': 'No active cart'}, status=400)

    data = _get_payload(request)
    customer_name = data.get('customer_name') or cart.customer_name
    notes = data.get('notes') or ''

    cart.customer_name = customer_name
    cart.notes = notes
    cart.save(update_fields=['customer_name', 'notes', 'updated_at'])

    if _is_htmx(request):
        resp = HttpResponse('')
        return _hx_trigger(resp, 'Details saved')

    return JsonResponse({'success': True})


@login_required
def search_customers(request):
    """Quick customer search."""
    query = request.GET.get('q', '').strip()
    try:
        limit = int(request.GET.get('limit', 5) or 5)
    except (ValueError, TypeError):
        limit = 5
    if len(query) < 2:
        if _is_htmx(request):
            return HttpResponse('<div class="text-center text-muted py-2">Type 2+ letters</div>')
        return JsonResponse({'customers': []})

    customers = Customer.objects.filter(
        organization=request.organization
    ).filter(
        models.Q(display_name__icontains=query) |
        models.Q(phone_number__icontains=query) |
        models.Q(email__icontains=query)
    ).order_by('customer_name')[:limit]

    if _is_htmx(request):
        return render(request, 'pos/fragments/customer_search_results.html', {
            'customers': customers
        })

    data = [{
        'id': c.customer_id,
        'name': c.display_name,
        'phone': getattr(c, 'phone_number', ''),
        'email': getattr(c, 'email', '')
    } for c in customers]
    return JsonResponse({'customers': data})


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


def render_held_orders(request):
    held_carts = Cart.objects.filter(
        user=request.user,
        organization=request.organization,
        status='held'
    ).order_by('-updated_at')[:10]
    return render(request, 'pos/fragments/held_orders.html', {
        'held_carts': held_carts
    }).content.decode('utf-8')
