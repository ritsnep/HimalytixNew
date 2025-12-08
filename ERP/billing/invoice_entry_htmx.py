# billing/views.py
"""
Sales Invoice Entry Views with HTMX
Interactive invoice creation with real-time calculations and customer search
"""
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from weasyprint import HTML

from inventory.models import Product
from accounting.ird_service import record_invoice_print
from accounting.models import (
    ChartOfAccount,
    Currency,
    Customer,
    JournalType,
    PaymentTerm,
    SalesInvoice,
    SalesInvoiceLine,
    TaxCode,
)
from accounting.services.ird_submission_service import IRDSubmissionService
from accounting.services.sales_invoice_service import SalesInvoiceService


@login_required
def invoice_create(request):
    """Main invoice creation page"""
    organization = request.user.organization

    revenue_accounts = ChartOfAccount.objects.filter(
        organization=organization,
        account_type__nature="income",
        is_active=True,
    ).order_by("account_name")

    tax_rates = TaxCode.objects.filter(
        organization=organization,
        is_active=True,
    ).order_by("rate")

    currencies = Currency.objects.filter(is_active=True).order_by("currency_code")
    # `organization.base_currency_code` is now a FK to Currency, so prefer that instance.
    default_currency = getattr(organization, 'base_currency_code', None) or currencies.first()

    payment_terms = PaymentTerm.objects.filter(
        organization=organization,
        is_active=True,
        term_type__in=["ar", "both"],
    ).order_by("name")

    journal_types = JournalType.objects.filter(organization=organization, is_active=True).order_by("name")

    context = {
        "revenue_accounts": revenue_accounts,
        "tax_rates": tax_rates,
        "currencies": currencies,
        "default_currency": default_currency,
        "payment_terms": payment_terms,
        "journal_types": journal_types,
        "today": date.today(),
    }

    return render(request, "billing/invoice_create.html", context)


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
        Q(display_name__icontains=query) |
        Q(legal_name__icontains=query) |
        Q(phone_number__icontains=query) |
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
    line_index = request.GET.get('line_index', '')
    
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
        'products': products,
        'line_index': line_index,
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
    tax_code_id = request.POST.get('tax_rate')
    tax_rate = Decimal(
        TaxCode.objects.filter(
            tax_code_id=tax_code_id,
            organization=request.user.organization,
        ).values_list('rate', flat=True).first() or 0
    )
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
        tax_code_id = request.POST.get(f'tax_rate_{idx}', '') or None
        tax_rate = Decimal(
            TaxCode.objects.filter(
                tax_code_id=tax_code_id,
                organization=request.user.organization,
            ).values_list('rate', flat=True).first() or 0
        )
        
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
    action = request.POST.get('action', 'save_draft')  # 'save_draft' or 'post'

    customer_id = request.POST.get('customer_id')
    if not customer_id:
        messages.error(request, "Select a customer before saving the invoice.")
        return redirect('billing:invoice_create')

    try:
        customer = Customer.objects.get(pk=customer_id, organization=organization)
    except Customer.DoesNotExist:
        messages.error(request, "Invalid customer selected.")
        return redirect('billing:invoice_create')

    try:
        invoice_date = datetime.fromisoformat(request.POST.get('invoice_date')).date()
    except Exception:
        messages.error(request, "Invoice date is required.")
        return redirect('billing:invoice_create')

    due_date_input = request.POST.get('due_date') or None
    due_date = None
    if due_date_input:
        try:
            due_date = datetime.fromisoformat(due_date_input).date()
        except Exception:
            messages.warning(request, "Could not parse due date; using payment term defaults.")

    # request may post a currency code; otherwise use organization's base currency FK
    currency_code = request.POST.get('currency') or getattr(organization, 'base_currency_code_id', None)
    currency = Currency.objects.filter(currency_code=currency_code).first()
    if not currency:
        messages.error(request, "Please configure at least one currency before creating invoices.")
        return redirect('billing:invoice_create')

    payment_term = None
    payment_term_id = request.POST.get('payment_term')
    if payment_term_id:
        payment_term = PaymentTerm.objects.filter(
            payment_term_id=payment_term_id,
            organization=organization,
            is_active=True,
        ).first()
    if not payment_term:
        payment_term = getattr(customer, 'payment_term', None)

    try:
        exchange_rate = Decimal(request.POST.get('exchange_rate') or "1")
    except Exception:
        exchange_rate = Decimal("1")

    line_indices = [int(idx) for idx in request.POST.getlist('line_index[]') if idx]
    line_indices.sort()
    lines = []
    for idx in line_indices:
        description = (request.POST.get(f'description_{idx}', '') or '').strip()
        if not description:
            continue

        revenue_account_id = request.POST.get(f'revenue_account_{idx}')
        revenue_account = ChartOfAccount.objects.filter(
            account_id=revenue_account_id,
            organization=organization,
        ).first()
        if not revenue_account:
            messages.error(request, "Each line needs a revenue account.")
            return redirect('billing:invoice_create')

        quantity = Decimal(request.POST.get(f'quantity_{idx}', 0) or 0)
        unit_price = Decimal(request.POST.get(f'unit_price_{idx}', 0) or 0)
        tax_code_id = request.POST.get(f'tax_rate_{idx}')
        tax_code = TaxCode.objects.filter(
            tax_code_id=tax_code_id,
            organization=organization,
        ).first()
        tax_rate = Decimal(tax_code.rate or 0) if tax_code else Decimal("0")
        line_subtotal = quantity * unit_price
        tax_amount = (line_subtotal * tax_rate) / Decimal("100")

        lines.append(
            {
                "description": description,
                "product_code": request.POST.get(f'product_code_{idx}', '') or '',
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_amount": Decimal("0"),
                "revenue_account": revenue_account,
                "tax_code": tax_code,
                "tax_amount": tax_amount,
            }
        )

    if not lines:
        messages.error(request, "Add at least one invoice line.")
        return redirect('billing:invoice_create')

    service = SalesInvoiceService(request.user)

    try:
        with transaction.atomic():
            invoice = service.create_invoice(
                organization=organization,
                customer=customer,
                invoice_number=None,
                invoice_date=invoice_date,
                currency=currency,
                lines=lines,
                payment_term=payment_term,
                due_date=due_date,
                exchange_rate=exchange_rate,
                metadata={},
            )
            invoice.reference_number = request.POST.get('reference_number', '') or ''
            invoice.notes = request.POST.get('notes', '') or ''
            invoice.save(update_fields=['reference_number', 'notes'])

            if action == 'post':
                service.validate_invoice(invoice)
                requested_journal_type = request.POST.get('journal_type')
                journal_type = (
                    JournalType.objects.filter(
                        journal_type_id=requested_journal_type,
                        organization=organization,
                    ).first()
                    if requested_journal_type
                    else JournalType.objects.filter(
                        organization=organization, code__icontains="sales"
                    ).order_by('journal_type_id').first()
                ) or JournalType.objects.filter(organization=organization).order_by('journal_type_id').first()

                if not journal_type:
                    messages.error(request, "No journal type is configured for posting sales invoices.")
                    return redirect('billing:invoice_detail', invoice_id=invoice.invoice_id)

                service.post_invoice(invoice, journal_type, submit_to_ird=True)
                messages.success(
                    request,
                    "Invoice posted. IRD submission has been queued.",
                )
            else:
                messages.success(request, "Draft invoice saved.")
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f'Error creating invoice: {exc}')
        return redirect('billing:invoice_create')

    return redirect('billing:invoice_detail', invoice_id=invoice.invoice_id)


@login_required
def invoice_detail(request, invoice_id):
    """View invoice details"""
    invoice = (
        SalesInvoice.objects.select_related('customer', 'currency', 'journal')
        .prefetch_related('lines')
        .filter(invoice_id=invoice_id, organization=request.user.organization)
        .first()
    )
    if not invoice:
        return redirect('billing:invoice_list')

    lines = invoice.lines.select_related('tax_code', 'revenue_account').all()
    
    # Get available journal types for posting
    journal_types = JournalType.objects.filter(
        organization=request.user.organization,
        is_active=True
    ).order_by('name')
    
    return render(
        request,
        'billing/invoice_detail.html',
        {
            'invoice': invoice,
            'lines': lines,
            'journal_types': journal_types,
        },
    )


@login_required
def invoice_list(request):
    """List all invoices with filters"""
    organization = request.user.organization
    invoices = SalesInvoice.objects.filter(
        organization=organization
    ).select_related('customer', 'currency').order_by('-invoice_date')

    # Status filter
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    # Date range filters
    date_from = request.GET.get('date_from')
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)
    
    # Customer filter
    customer_id = request.GET.get('customer')
    if customer_id:
        invoices = invoices.filter(customer_id=customer_id)
    
    # Currency filter
    currency_code = request.GET.get('currency')
    if currency_code:
        invoices = invoices.filter(currency__currency_code=currency_code)
    
    # IRD status filter
    ird_status = request.GET.get('ird_status')
    if ird_status:
        invoices = invoices.filter(ird_status=ird_status)

    paginator = Paginator(invoices, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options for dropdowns
    customers = Customer.objects.filter(
        organization=organization,
        is_active=True
    ).order_by('display_name')
    
    currencies = Currency.objects.filter(is_active=True).order_by('currency_code')

    return render(request, 'billing/invoice_list.html', {
        'invoices': page_obj,
        'status_choices': SalesInvoice.STATUS_CHOICES,
        'ird_status_choices': [
            ('pending', 'Pending'),
            ('synced', 'Synced'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        'customers': customers,
        'currencies': currencies,
        # Pass current filter values for maintaining form state
        'current_status': status or '',
        'current_customer': customer_id or '',
        'current_currency': currency_code or '',
        'current_ird_status': ird_status or '',
        'current_date_from': date_from or '',
        'current_date_to': date_to or '',
    })


@login_required
def invoice_pdf(request, invoice_id):
    """Generate PDF with QR code for IRD-synced invoices"""
    invoice = (
        SalesInvoice.objects.select_related('customer', 'currency')
        .prefetch_related('lines')
        .filter(invoice_id=invoice_id, organization=request.user.organization)
        .first()
    )
    if not invoice:
        return redirect('billing:invoice_list')

    # Generate QR code if invoice is synced with IRD
    qr_base64 = None
    if invoice.ird_status == 'synced' and invoice.ird_qr_data:
        try:
            import qrcode
            from io import BytesIO
            import base64
            
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(invoice.ird_qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        except Exception:
            pass  # QR generation failed, continue without it

    html_string = render_to_string(
        'billing/invoice_pdf.html',
        {
            'invoice': invoice,
            'lines': invoice.lines.all(),
            'qr_base64': qr_base64,
        },
    )

    html = HTML(string=html_string)
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Invoice-{invoice.invoice_number}.pdf"'

    try:
        record_invoice_print(invoice)
    except Exception:  # noqa: BLE001
        logger = __import__("logging").getLogger(__name__)
        logger.warning("ird.print_log_failed", exc_info=True)

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

    if invoice.status != 'posted':
        messages.error(request, 'Only posted invoices can be sent to IRD.')
        return redirect('billing:invoice_detail', invoice_id=invoice_id)

    service = IRDSubmissionService(request.user)
    task = service.enqueue_invoice(invoice)
    if invoice.ird_status != 'pending':
        invoice.ird_status = 'pending'
        invoice.save(update_fields=['ird_status', 'updated_at'])
    messages.success(
        request,
        f'Invoice queued for IRD submission (task #{task.submission_id}).',
    )

    return redirect('billing:invoice_detail', invoice_id=invoice_id)


@login_required
@require_POST
def post_invoice(request, invoice_id):
    """Post a draft or validated invoice"""
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=request.user.organization
    )
    
    if invoice.status not in ['draft', 'validated']:
        messages.error(request, 'Only draft or validated invoices can be posted.')
        return redirect('billing:invoice_detail', invoice_id=invoice_id)
    
    organization = request.user.organization
    
    # Get journal type from request or use default
    journal_type_id = request.POST.get('journal_type')
    if journal_type_id:
        journal_type = JournalType.objects.filter(
            journal_type_id=journal_type_id,
            organization=organization,
            is_active=True
        ).first()
    else:
        # Try to find a sales-related journal type
        journal_type = JournalType.objects.filter(
            organization=organization,
            code__icontains='sales',
            is_active=True
        ).first()
    
    if not journal_type:
        # Fallback to any active journal type
        journal_type = JournalType.objects.filter(
            organization=organization,
            is_active=True
        ).first()
    
    if not journal_type:
        messages.error(request, 'No journal type configured for posting.')
        return redirect('billing:invoice_detail', invoice_id=invoice_id)
    
    # Get warehouse if needed for inventory items
    from inventory.models import Warehouse
    warehouse = Warehouse.objects.filter(
        organization=organization,
        is_active=True
    ).first()
    
    # Determine whether to auto-submit to IRD
    submit_to_ird = request.POST.get('submit_to_ird') == 'true'
    
    try:
        service = SalesInvoiceService(request.user)
        
        # Validate first if not already validated
        if invoice.status == 'draft':
            service.validate_invoice(invoice)
        
        # Post the invoice
        journal = service.post_invoice(
            invoice,
            journal_type,
            submit_to_ird=submit_to_ird,
            warehouse=warehouse
        )
        
        messages.success(
            request,
            f'Invoice #{invoice.invoice_number} posted successfully. Journal #{journal.journal_number} created.'
        )
        
        if submit_to_ird and invoice.ird_status == 'pending':
            messages.info(request, 'Invoice has been queued for IRD submission.')
            
    except ValidationError as e:
        messages.error(request, f'Validation error: {e.message}')
    except Exception as e:
        messages.error(request, f'Error posting invoice: {str(e)}')
    
    return redirect('billing:invoice_detail', invoice_id=invoice_id)


@login_required
def send_to_ird(request, invoice_id):
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=request.user.organization
    )

    if invoice.ird_status == 'synced':
        messages.warning(request, 'Invoice already submitted to IRD')
        return redirect('billing:invoice_detail', invoice_id=invoice_id)

    if invoice.status != 'posted':
        messages.error(request, 'Only posted invoices can be sent to IRD.')
        return redirect('billing:invoice_detail', invoice_id=invoice_id)

    service = IRDSubmissionService(request.user)
    task = service.enqueue_invoice(invoice)
    if invoice.ird_status != 'pending':
        invoice.ird_status = 'pending'
        invoice.save(update_fields=['ird_status', 'updated_at'])
    messages.success(
        request,
        f'Invoice queued for IRD submission (task #{task.submission_id}).',
    )

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
        invoice.ird_status = 'cancelled'
        messages.warning(request, 'Marked IRD status as cancelled. Please ensure the cancellation is reflected on the IRD portal if required.')

    invoice.status = 'cancelled'
    if reason:
        invoice.notes = f"{invoice.notes}\nCancelled: {reason}".strip()
    invoice.save(update_fields=['status', 'notes', 'ird_status', 'updated_at'])

    messages.success(request, 'Invoice cancelled.')
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
