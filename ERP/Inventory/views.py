from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import StockReceiptForm, StockIssueForm
from .models import Batch, InventoryItem
from .services import InventoryService

def dashboard(request):
    return render(request, 'inventory/dashboard.html')

def products(request):
    return render(request, 'inventory/products.html')

def categories(request):
    return render(request, 'inventory/categories.html')

def warehouses(request):
    return render(request, 'inventory/warehouses.html')

def stock_movements(request):
    return render(request, 'inventory/stock_movements.html')


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
