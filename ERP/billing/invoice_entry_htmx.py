# billing/views.py
"""
Sales Invoice Entry Views with HTMX
Interactive invoice creation with real-time calculations and customer search
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from datetime import date, datetime
import uuid

from accounting.models import (
    SalesInvoice, SalesInvoiceLine, Customer, 
    ChartOfAccount, TaxCode, Organization
)
from Inventory.models import Product
from accounting.services.ird_ebilling import IRDEBillingService
from django.core.paginator import Paginator
from django.utils import timezone
from django.template.loader import render_to_string
from weasyprint import HTML
from django.views.decorators.http import require_POST
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.http import HttpResponse
from django.contrib.auth.decorators import permission_required


@login_required
def invoice_create(request):
    """Main invoice creation page"""
    organization = request.user.organization
    
    # Get default accounts for dropdown
    revenue_accounts = ChartOfAccount.objects.filter(
        organization=organization,
        account_type__nature='income',
        is_active=True
    ).order_by('account_name')
    
    tax_rates = TaxCode.objects.filter(
        organization=organization,
        is_active=True
    ).order_by('rate')
    
    context = {
        'revenue_accounts': revenue_accounts,
        'tax_rates': tax_rates,
        'today': date.today(),
    }
    
    return render(request, 'billing/invoice_create.html', context)


@login_required
def customer_search(request):
    """HTMX endpoint: Search customers as user types"""
    query = request.GET.get('q', '').strip()
    organization = request.user.organization
    
    if len(query) < 2:
        return HttpResponse('')
    
    customers = Customer.objects.filter(
        organization=organization,
        is_active=True
    ).filter(
        Q(customer_name__icontains=query) |
        Q(contact_person__icontains=query) |
        Q(phone__icontains=query) |
        Q(tax_id__icontains=query)
    )[:10]
    
    return render(request, 'billing/partials/customer_results.html', {
        'customers': customers
    })


@login_required
def product_search(request):
    """HTMX endpoint: Search products for invoice line"""
    query = request.GET.get('q', '').strip()
    organization = request.user.organization
    
    if len(query) < 2:
        return HttpResponse('')
    
    products = Product.objects.filter(
        organization=organization,
        is_active=True
    ).filter(
        Q(name__icontains=query) |
        Q(code__icontains=query)
    )[:10]
    
    return render(request, 'billing/partials/product_results.html', {
        'products': products
    })


@login_required
def add_invoice_line(request):
    """HTMX endpoint: Add new invoice line row"""
    line_index = request.GET.get('index', 1)
    organization = request.user.organization
    
    revenue_accounts = ChartOfAccount.objects.filter(
        organization=organization,
        account_type__nature='income',
        is_active=True
    )
    
    # Use TaxCode model (existing) for available tax rates/codes
    tax_rates = TaxCode.objects.filter(
        organization=organization,
        is_active=True
    ).order_by('rate')
    
    return render(request, 'billing/partials/invoice_line_row.html', {
        'line_index': line_index,
        'revenue_accounts': revenue_accounts,
        'tax_rates': tax_rates,
    })


@login_required
def calculate_line_total(request):
    """HTMX endpoint: Calculate line total when quantity/price changes"""
    quantity = Decimal(request.POST.get('quantity', 0))
    unit_price = Decimal(request.POST.get('unit_price', 0))
    tax_rate = Decimal(request.POST.get('tax_rate', 0))
    line_index = request.POST.get('line_index', 0)
    
    # Calculate amounts
    line_subtotal = quantity * unit_price
    tax_amount = (line_subtotal * tax_rate) / 100
    line_total = line_subtotal + tax_amount
    
    return render(request, 'billing/partials/line_total_display.html', {
        'line_index': line_index,
        'line_subtotal': line_subtotal,
        'tax_amount': tax_amount,
        'line_total': line_total,
    })


@login_required
def calculate_invoice_total(request):
    """HTMX endpoint: Recalculate invoice totals"""
    # Get all line totals from form
    line_indices = request.POST.getlist('line_index[]')
    
    subtotal = Decimal(0)
    tax_total = Decimal(0)
    
    for idx in line_indices:
        quantity = Decimal(request.POST.get(f'quantity_{idx}', 0) or 0)
        unit_price = Decimal(request.POST.get(f'unit_price_{idx}', 0) or 0)
        tax_rate = Decimal(request.POST.get(f'tax_rate_{idx}', 0) or 0)
        
        line_subtotal = quantity * unit_price
        line_tax = (line_subtotal * tax_rate) / 100
        
        subtotal += line_subtotal
        tax_total += line_tax
    
    # Apply discount if any
    discount_percent = Decimal(request.POST.get('discount_percent', 0) or 0)
    discount_amount = (subtotal * discount_percent) / 100
    
    total = subtotal - discount_amount + tax_total
    
    return render(request, 'billing/partials/invoice_totals.html', {
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'tax_total': tax_total,
        'total': total,
    })


@login_required
def invoice_save(request):
    """Save invoice (draft or posted)"""
    if request.method != 'POST':
        return redirect('invoice_create')
    
    organization = request.user.organization
    action = request.POST.get('action')  # 'save_draft' or 'post'
    
    try:
        with transaction.atomic():
            # Create invoice header
            invoice = SalesInvoice()
            invoice.organization = organization
            invoice.invoice_date = request.POST.get('invoice_date')
            invoice.due_date = request.POST.get('due_date')
            
            # Customer
            customer_id = request.POST.get('customer_id')
            if customer_id:
                invoice.customer = Customer.objects.get(pk=customer_id)
                invoice.customer_display_name = invoice.customer.customer_name
            else:
                invoice.customer_display_name = request.POST.get('customer_name')
            
            # Reference and notes
            invoice.reference_number = request.POST.get('reference_number', '')
            invoice.notes = request.POST.get('notes', '')
            
            # Amounts (will recalculate from lines)
            invoice.subtotal = Decimal(0)
            invoice.tax_total = Decimal(0)
            invoice.discount_amount = Decimal(request.POST.get('discount_amount', 0) or 0)
            
            # Status
            if action == 'post':
                invoice.status = 'posted'
                invoice.posted_at = datetime.now()
                invoice.posted_by = request.user
            else:
                invoice.status = 'draft'
            
            invoice.save()
            
            # Generate invoice number
            invoice.invoice_number = f"INV-{invoice.invoice_date.year}-{invoice.invoice_id:06d}"
            invoice.save(update_fields=['invoice_number'])
            
            # Create invoice lines
            line_indices = request.POST.getlist('line_index[]')
            
            for idx in line_indices:
                description = request.POST.get(f'description_{idx}')
                if not description:
                    continue
                
                line = SalesInvoiceLine()
                line.invoice = invoice
                line.line_number = int(idx)
                line.description = description
                line.quantity = Decimal(request.POST.get(f'quantity_{idx}', 0))
                line.unit_price = Decimal(request.POST.get(f'unit_price_{idx}', 0))
                
                # Product if selected
                product_id = request.POST.get(f'product_id_{idx}')
                if product_id:
                    line.product = Product.objects.get(pk=product_id)
                    line.product_code = line.product.code
                
                # Revenue account
                account_id = request.POST.get(f'revenue_account_{idx}')
                if account_id:
                    line.revenue_account = ChartOfAccount.objects.get(pk=account_id)
                
                # Tax
                tax_rate_id = request.POST.get(f'tax_rate_{idx}')
                if tax_rate_id:
                    from accounting.models import TaxCode
                    line.tax_rate = TaxCode.objects.get(pk=tax_rate_id)
                    line.tax_percent = line.tax_rate.rate
                
                # Calculate line amounts
                line_subtotal = line.quantity * line.unit_price
                line.tax_amount = (line_subtotal * line.tax_percent) / 100
                line.line_total = line_subtotal + line.tax_amount
                
                line.save()
                
                # Update invoice totals
                invoice.subtotal += line_subtotal
                invoice.tax_total += line.tax_amount
            
            # Final total
            invoice.total = invoice.subtotal - invoice.discount_amount + invoice.tax_total
            invoice.save(update_fields=['subtotal', 'tax_total', 'total'])
            
            # If posted, submit to IRD
            if action == 'post':
                ird_service = IRDEBillingService(organization)
                ird_result = ird_service.submit_invoice(invoice)
                
                if ird_result['success']:
                    messages.success(
                        request,
                        f'Invoice {invoice.invoice_number} created and submitted to IRD. '
                        f'Acknowledgment ID: {ird_result["ack_id"]}'
                    )
                else:
                    messages.warning(
                        request,
                        f'Invoice {invoice.invoice_number} created but IRD submission failed: '
                        f'{ird_result["error"]}'
                    )
            else:
                messages.success(request, f'Draft invoice {invoice.invoice_number} saved.')
            
            return redirect('billing:invoice_detail', invoice_id=invoice.invoice_id)
    
    except Exception as e:
        messages.error(request, f'Error creating invoice: {str(e)}')
        return redirect('billing:invoice_create')


@login_required
def invoice_detail(request, invoice_id):
    """View invoice details"""
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=request.user.organization
    )
    
    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice
    })


@login_required
def invoice_list(request):
    """List all invoices with filters"""
    organization = request.user.organization
    invoices = SalesInvoice.objects.filter(
        organization=organization
    ).select_related('customer').order_by('-invoice_date')

    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    date_from = request.GET.get('date_from')
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)

    paginator = Paginator(invoices, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'billing/invoice_list.html', {
        'invoices': page_obj,
        'status_choices': SalesInvoice.STATUS_CHOICES,
    })


@login_required
def invoice_pdf(request, invoice_id):
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=request.user.organization
    )

    qr_base64 = None
    if invoice.ird_status == 'synced' and invoice.ird_qr_data:
        ird_service = IRDEBillingService(invoice.organization)
        qr_image = ird_service.generate_qr_code_image(invoice.ird_qr_data)
        import base64
        qr_base64 = base64.b64encode(qr_image.getvalue()).decode()

    html_string = render_to_string('billing/invoice_pdf.html', {
        'invoice': invoice,
        'qr_base64': qr_base64
    })

    html = HTML(string=html_string)
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice-{invoice.invoice_number}.pdf"'

    # Log print to IRD
    ird_service = IRDEBillingService(invoice.organization)
    try:
        ird_service.print_invoice(invoice)
    except Exception:
        pass

    return response


@login_required
def submit_to_ird(request, invoice_id):
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=request.user.organization
    )

    if invoice.ird_status == 'synced':
        messages.warning(request, 'Invoice already submitted to IRD')
        return redirect('billing:invoice_detail', invoice_id=invoice_id)

    ird_service = IRDEBillingService(invoice.organization)
    result = ird_service.submit_invoice(invoice)

    if result.get('success'):
        messages.success(request, f'Invoice submitted to IRD successfully. Ack ID: {result.get("ack_id")}')
    else:
        messages.error(request, f'IRD submission failed: {result.get("error")}')

    return redirect('billing:invoice_detail', invoice_id=invoice_id)


@login_required
def cancel_invoice(request, invoice_id):
    if request.method != 'POST':
        return redirect('billing:invoice_detail', invoice_id=invoice_id)

    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=request.user.organization
    )

    reason = request.POST.get('reason', '')

    if invoice.ird_status == 'synced':
        ird_service = IRDEBillingService(invoice.organization)
        result = ird_service.cancel_invoice(invoice, reason)
        if not result.get('success'):
            messages.error(request, f'IRD cancellation failed: {result.get("error")}')
            return redirect('billing:invoice_detail', invoice_id=invoice_id)

    invoice.status = 'cancelled'
    invoice.cancelled_at = timezone.now()
    invoice.cancelled_by = request.user
    invoice.cancellation_reason = reason
    invoice.save()

    messages.success(request, 'Invoice cancelled successfully')
    return redirect('billing:invoice_detail', invoice_id=invoice_id)


@login_required
def export_tally(request):
    organization = request.user.organization
    if request.method == 'GET':
        return render(request, 'billing/export_tally.html')

    start_date = request.POST.get('start_date')
    end_date = request.POST.get('end_date')

    invoices = SalesInvoice.objects.filter(
        organization=organization,
        status='posted',
        invoice_date__range=[start_date, end_date]
    )

    from accounting.services.tally_export import TallyXMLExporter
    exporter = TallyXMLExporter(organization.name)
    xml_data = exporter.export_sales_invoices(invoices, start_date, end_date)

    response = HttpResponse(xml_data, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="tally_export_{start_date}_{end_date}.xml"'
    return response


# URL Configuration (add to billing/urls.py)
"""
from django.urls import path
from billing import views

urlpatterns = [
    path('invoice/create/', views.invoice_create, name='invoice_create'),
    path('invoice/<uuid:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/save/', views.invoice_save, name='invoice_save'),
    
    # HTMX endpoints
    path('htmx/customer-search/', views.customer_search, name='customer_search'),
    path('htmx/product-search/', views.product_search, name='product_search'),
    path('htmx/add-line/', views.add_invoice_line, name='add_invoice_line'),
    path('htmx/calculate-line/', views.calculate_line_total, name='calculate_line_total'),
    path('htmx/calculate-total/', views.calculate_invoice_total, name='calculate_invoice_total'),
]
"""
