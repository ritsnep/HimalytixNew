# accounting/views/ird_invoice_views.py
"""
Comprehensive Django views for IRD E-Billing integrated sales invoice system
Handles invoice creation, submission, printing, cancellation, and QR code generation
"""
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.core.paginator import Paginator
from django.forms import inlineformset_factory

from accounting.models import (
    SalesInvoice, 
    SalesInvoiceLine, 
    Customer, 
    Organization,
    ChartOfAccount,
    TaxCode,
    Currency,
    PaymentTerm,
    DocumentSequenceConfig,
)
from accounting.forms.commerce_forms import SalesInvoiceForm, SalesInvoiceLineForm
from accounting.services.ird_ebilling import IRDEBillingService
from accounting.services.sales_invoice_service import SalesInvoiceService


# =============================================
# Sales Invoice List View
# =============================================
class SalesInvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Display paginated list of sales invoices with filtering and IRD status
    """
    model = SalesInvoice
    template_name = 'accounting/sales_invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 25
    permission_required = 'accounting.view_salesinvoice'
    
    def get_queryset(self):
        organization = self.request.user.organization
        queryset = SalesInvoice.objects.filter(
            organization=organization
        ).select_related(
            'customer', 
            'currency', 
            'payment_term'
        ).prefetch_related('lines')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by IRD status
        ird_status = self.request.GET.get('ird_status')
        if ird_status:
            queryset = queryset.filter(ird_status=ird_status)
        
        # Filter by customer
        customer_id = self.request.GET.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        # Search by invoice number or customer name
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(customer_display_name__icontains=search)
            )
        
        # Date range filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        
        return queryset.order_by('-invoice_date', '-invoice_id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.organization
        
        # Summary statistics
        context['total_invoices'] = self.get_queryset().count()
        context['pending_ird'] = self.get_queryset().filter(
            Q(ird_status__isnull=True) | Q(ird_status='pending')
        ).count()
        context['synced_ird'] = self.get_queryset().filter(ird_status='synced').count()
        context['failed_ird'] = self.get_queryset().filter(ird_status='failed').count()
        
        # Filter options
        context['customers'] = Customer.objects.filter(
            organization=organization, 
            is_active=True
        ).order_by('name')
        context['status_choices'] = SalesInvoice.STATUS_CHOICES
        
        # Preserve filters
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'ird_status': self.request.GET.get('ird_status', ''),
            'customer': self.request.GET.get('customer', ''),
            'search': self.request.GET.get('search', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
        }
        
        return context


# =============================================
# Sales Invoice Detail View with QR Code
# =============================================
class SalesInvoiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Display detailed invoice with IRD information and QR code
    """
    model = SalesInvoice
    template_name = 'accounting/sales_invoice_detail.html'
    context_object_name = 'invoice'
    permission_required = 'accounting.view_salesinvoice'
    pk_url_kwarg = 'invoice_id'
    
    def get_queryset(self):
        return SalesInvoice.objects.filter(
            organization=self.request.user.organization
        ).select_related('customer', 'currency', 'payment_term')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object
        
        # Generate QR code if IRD synced
        if invoice.ird_status == 'synced' and invoice.ird_ack_id:
            ird_service = IRDEBillingService(self.request.user.organization)
            qr_data = ird_service._generate_qr_data(invoice, {
                'acknowledgment_id': invoice.ird_ack_id,
                'signature': invoice.ird_signature
            })
            context['qr_data'] = qr_data
        
        # Invoice lines
        context['lines'] = invoice.lines.select_related(
            'revenue_account', 'tax_code'
        ).order_by('line_number')
        
        return context


# =============================================
# Sales Invoice Create/Edit View
# =============================================
class SalesInvoiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Create new sales invoice with inline line items
    Supports both AJAX and standard form submission
    """
    permission_required = 'accounting.add_salesinvoice'
    template_name = 'accounting/sales_invoice_form.html'
    
    def get(self, request):
        organization = request.user.organization
        
        # Create formset for invoice lines
        SalesInvoiceLineFormSet = inlineformset_factory(
            SalesInvoice,
            SalesInvoiceLine,
            form=SalesInvoiceLineForm,
            extra=5,
            can_delete=True,
            min_num=1,
            validate_min=True,
        )
        
        form = SalesInvoiceForm(organization=organization)
        formset = SalesInvoiceLineFormSet()
        
        context = {
            'form': form,
            'formset': formset,
            'organization': organization,
            'customers': Customer.objects.filter(
                organization=organization, 
                is_active=True
            ),
            'revenue_accounts': ChartOfAccount.objects.filter(
                organization=organization,
                account_type__in=['revenue', 'income'],
                is_active=True
            ),
            'tax_codes': TaxCode.objects.filter(
                organization=organization,
                is_active=True
            ),
            'currencies': Currency.objects.filter(is_active=True),
        }
        
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request):
        organization = request.user.organization
        
        SalesInvoiceLineFormSet = inlineformset_factory(
            SalesInvoice,
            SalesInvoiceLine,
            form=SalesInvoiceLineForm,
            extra=0,
            can_delete=True,
            min_num=1,
            validate_min=True,
        )
        
        form = SalesInvoiceForm(request.POST, organization=organization)
        
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.organization = organization
            invoice.created_by = request.user
            invoice.updated_by = request.user
            
            # Set customer display name
            if invoice.customer:
                invoice.customer_display_name = invoice.customer.name
            
            invoice.save()
            
            # Process line items
            formset = SalesInvoiceLineFormSet(request.POST, instance=invoice)
            if formset.is_valid():
                formset.save()
                
                # Recompute totals
                invoice.recompute_totals(save=True)
                
                # Check if should auto-submit to IRD
                auto_submit = request.POST.get('auto_submit_ird') == 'on'
                if auto_submit and invoice.status == 'posted':
                    return redirect('accounting:invoice_submit_ird', invoice_id=invoice.invoice_id)
                
                messages.success(request, f'Invoice {invoice.invoice_number} created successfully.')
                return redirect('accounting:invoice_detail', invoice_id=invoice.invoice_id)
            else:
                # Formset errors
                messages.error(request, 'Please correct the errors in invoice lines.')
        else:
            formset = SalesInvoiceLineFormSet(request.POST)
            messages.error(request, 'Please correct the errors in the form.')
        
        context = {
            'form': form,
            'formset': formset,
            'organization': organization,
            'customers': Customer.objects.filter(
                organization=organization, 
                is_active=True
            ),
            'revenue_accounts': ChartOfAccount.objects.filter(
                organization=organization,
                account_type__in=['revenue', 'income'],
                is_active=True
            ),
            'tax_codes': TaxCode.objects.filter(
                organization=organization,
                is_active=True
            ),
        }
        
        return render(request, self.template_name, context)


# =============================================
# Sales Invoice Update View
# =============================================
class SalesInvoiceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Edit existing sales invoice (only if not posted or synced to IRD)
    """
    permission_required = 'accounting.change_salesinvoice'
    template_name = 'accounting/sales_invoice_form.html'
    
    def get(self, request, invoice_id):
        organization = request.user.organization
        invoice = get_object_or_404(
            SalesInvoice, 
            invoice_id=invoice_id,
            organization=organization
        )
        
        # Prevent editing posted/synced invoices
        if invoice.status == 'posted':
            messages.error(request, 'Cannot edit posted invoice.')
            return redirect('accounting:invoice_detail', invoice_id=invoice_id)
        
        if invoice.ird_status == 'synced':
            messages.error(request, 'Cannot edit invoice synced with IRD.')
            return redirect('accounting:invoice_detail', invoice_id=invoice_id)
        
        SalesInvoiceLineFormSet = inlineformset_factory(
            SalesInvoice,
            SalesInvoiceLine,
            form=SalesInvoiceLineForm,
            extra=2,
            can_delete=True,
            min_num=1,
            validate_min=True,
        )
        
        form = SalesInvoiceForm(instance=invoice, organization=organization)
        formset = SalesInvoiceLineFormSet(instance=invoice)
        
        context = {
            'form': form,
            'formset': formset,
            'invoice': invoice,
            'organization': organization,
            'is_edit': True,
            'customers': Customer.objects.filter(
                organization=organization, 
                is_active=True
            ),
            'revenue_accounts': ChartOfAccount.objects.filter(
                organization=organization,
                account_type__in=['revenue', 'income'],
                is_active=True
            ),
            'tax_codes': TaxCode.objects.filter(
                organization=organization,
                is_active=True
            ),
        }
        
        return render(request, self.template_name, context)
    
    @transaction.atomic
    def post(self, request, invoice_id):
        organization = request.user.organization
        invoice = get_object_or_404(
            SalesInvoice, 
            invoice_id=invoice_id,
            organization=organization
        )
        
        if invoice.status == 'posted' or invoice.ird_status == 'synced':
            messages.error(request, 'Cannot edit posted/synced invoice.')
            return redirect('accounting:invoice_detail', invoice_id=invoice_id)
        
        SalesInvoiceLineFormSet = inlineformset_factory(
            SalesInvoice,
            SalesInvoiceLine,
            form=SalesInvoiceLineForm,
            extra=0,
            can_delete=True,
            min_num=1,
            validate_min=True,
        )
        
        form = SalesInvoiceForm(request.POST, instance=invoice, organization=organization)
        
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.updated_by = request.user
            invoice.save()
            
            formset = SalesInvoiceLineFormSet(request.POST, instance=invoice)
            if formset.is_valid():
                formset.save()
                invoice.recompute_totals(save=True)
                
                messages.success(request, f'Invoice {invoice.invoice_number} updated successfully.')
                return redirect('accounting:invoice_detail', invoice_id=invoice.invoice_id)
            else:
                messages.error(request, 'Please correct the errors in invoice lines.')
        else:
            formset = SalesInvoiceLineFormSet(request.POST, instance=invoice)
            messages.error(request, 'Please correct the errors in the form.')
        
        context = {
            'form': form,
            'formset': formset,
            'invoice': invoice,
            'organization': organization,
            'is_edit': True,
        }
        
        return render(request, self.template_name, context)


# =============================================
# IRD Invoice Submission View
# =============================================
@login_required
@permission_required('accounting.change_salesinvoice', raise_exception=True)
@transaction.atomic
def submit_invoice_to_ird(request, invoice_id):
    """
    Submit sales invoice to IRD e-billing system
    Returns JSON response for AJAX or redirects for standard request
    """
    organization = request.user.organization
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=organization
    )
    
    # Validation
    if invoice.ird_status == 'synced':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Invoice already submitted to IRD'
            }, status=400)
        messages.warning(request, 'Invoice already submitted to IRD.')
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)
    
    if invoice.status != 'posted':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Invoice must be posted before IRD submission'
            }, status=400)
        messages.error(request, 'Invoice must be posted before IRD submission.')
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)
    
    # Submit to IRD
    ird_service = IRDEBillingService(organization)
    result = ird_service.submit_invoice(invoice)
    
    if result['success']:
        invoice.refresh_from_db()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'ird_ack_id': result['ack_id'],
                'ird_signature': result['ird_signature'],
                'qr_data': result['qr_data'],
                'message': f'Invoice submitted to IRD successfully. Ack ID: {result["ack_id"]}'
            })
        
        messages.success(
            request, 
            f'Invoice submitted to IRD successfully. Acknowledgment ID: {result["ack_id"]}'
        )
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'IRD submission failed')
            }, status=400)
        
        messages.error(request, f'IRD submission failed: {result.get("error")}')
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)


# =============================================
# IRD Invoice Cancellation View
# =============================================
@login_required
@permission_required('accounting.change_salesinvoice', raise_exception=True)
@transaction.atomic
def cancel_invoice_in_ird(request, invoice_id):
    """
    Cancel invoice in IRD system
    """
    organization = request.user.organization
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=organization
    )
    
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', '')
        
        if not reason:
            messages.error(request, 'Cancellation reason is required.')
            return redirect('accounting:invoice_detail', invoice_id=invoice_id)
        
        if invoice.ird_status != 'synced':
            messages.error(request, 'Only IRD-synced invoices can be cancelled.')
            return redirect('accounting:invoice_detail', invoice_id=invoice_id)
        
        # Cancel in IRD
        ird_service = IRDEBillingService(organization)
        result = ird_service.cancel_invoice(invoice, reason)
        
        if result['success']:
            messages.success(request, 'Invoice cancelled in IRD successfully.')
        else:
            messages.error(request, f'IRD cancellation failed: {result.get("error")}')
        
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)
    
    # GET request - show confirmation form
    context = {
        'invoice': invoice,
    }
    return render(request, 'accounting/invoice_cancel_confirm.html', context)


# =============================================
# Invoice Print/Reprint View
# =============================================
@login_required
@permission_required('accounting.view_salesinvoice', raise_exception=True)
def print_invoice(request, invoice_id):
    """
    Print invoice and track reprint count for IRD compliance
    """
    organization = request.user.organization
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=organization
    )
    
    # Log print/reprint to IRD
    if invoice.ird_status == 'synced':
        ird_service = IRDEBillingService(organization)
        ird_service.print_invoice(invoice)
        invoice.refresh_from_db()
    
    # Generate QR code
    qr_image = None
    qr_data = None
    if invoice.ird_status == 'synced' and invoice.ird_ack_id:
        ird_service = IRDEBillingService(organization)
        qr_data = ird_service._generate_qr_data(invoice, {
            'acknowledgment_id': invoice.ird_ack_id,
            'signature': invoice.ird_signature
        })
        # Generate QR code image
        qr_buffer = ird_service.generate_qr_code_image(qr_data)
        import base64
        qr_image = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')
    
    context = {
        'invoice': invoice,
        'lines': invoice.lines.select_related('revenue_account', 'tax_code').order_by('line_number'),
        'organization': organization,
        'qr_image': qr_image,
        'qr_data': qr_data,
        'is_reprint': invoice.ird_reprint_count > 1,
    }
    
    return render(request, 'accounting/invoice_print.html', context)


# =============================================
# Get QR Code Image (AJAX)
# =============================================
@login_required
def get_invoice_qr_code(request, invoice_id):
    """
    Generate and return QR code image for invoice
    """
    organization = request.user.organization
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=organization
    )
    
    if invoice.ird_status != 'synced' or not invoice.ird_ack_id:
        return HttpResponseBadRequest('QR code only available for IRD-synced invoices')
    
    ird_service = IRDEBillingService(organization)
    qr_data = ird_service._generate_qr_data(invoice, {
        'acknowledgment_id': invoice.ird_ack_id,
        'signature': invoice.ird_signature
    })
    
    qr_buffer = ird_service.generate_qr_code_image(qr_data)
    
    return HttpResponse(qr_buffer.getvalue(), content_type='image/png')


# =============================================
# Batch IRD Submission View
# =============================================
@login_required
@permission_required('accounting.change_salesinvoice', raise_exception=True)
def batch_submit_to_ird(request):
    """
    Submit multiple invoices to IRD in batch
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)
    
    organization = request.user.organization
    invoice_ids = request.POST.getlist('invoice_ids[]')
    
    if not invoice_ids:
        return JsonResponse({'error': 'No invoices selected'}, status=400)
    
    ird_service = IRDEBillingService(organization)
    results = {
        'success': [],
        'failed': [],
        'total': len(invoice_ids)
    }
    
    for invoice_id in invoice_ids:
        try:
            invoice = SalesInvoice.objects.get(
                invoice_id=invoice_id,
                organization=organization,
                status='posted'
            )
            
            if invoice.ird_status == 'synced':
                results['failed'].append({
                    'invoice_id': invoice_id,
                    'invoice_number': invoice.invoice_number,
                    'error': 'Already synced'
                })
                continue
            
            result = ird_service.submit_invoice(invoice)
            
            if result['success']:
                results['success'].append({
                    'invoice_id': invoice_id,
                    'invoice_number': invoice.invoice_number,
                    'ack_id': result['ack_id']
                })
            else:
                results['failed'].append({
                    'invoice_id': invoice_id,
                    'invoice_number': invoice.invoice_number,
                    'error': result.get('error', 'Unknown error')
                })
        
        except SalesInvoice.DoesNotExist:
            results['failed'].append({
                'invoice_id': invoice_id,
                'error': 'Invoice not found'
            })
    
    return JsonResponse(results)


# =============================================
# Invoice Post/Unpost View
# =============================================
@login_required
@permission_required('accounting.change_salesinvoice', raise_exception=True)
@transaction.atomic
def post_invoice(request, invoice_id):
    """
    Post invoice and optionally submit to IRD
    """
    organization = request.user.organization
    invoice = get_object_or_404(
        SalesInvoice,
        invoice_id=invoice_id,
        organization=organization
    )
    
    if invoice.status == 'posted':
        messages.warning(request, 'Invoice is already posted.')
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)
    
    # Use service to post invoice
    service = SalesInvoiceService(organization)
    
    try:
        # Post invoice (creates journal entries)
        service.post_invoice(invoice, user=request.user)
        
        # Check if should auto-submit to IRD
        auto_submit = request.POST.get('auto_submit_ird') == 'true'
        if auto_submit:
            ird_service = IRDEBillingService(organization)
            result = ird_service.submit_invoice(invoice)
            
            if result['success']:
                messages.success(
                    request,
                    f'Invoice posted and submitted to IRD. Ack ID: {result["ack_id"]}'
                )
            else:
                messages.warning(
                    request,
                    f'Invoice posted successfully, but IRD submission failed: {result.get("error")}'
                )
        else:
            messages.success(request, 'Invoice posted successfully.')
        
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)
    
    except Exception as e:
        messages.error(request, f'Failed to post invoice: {str(e)}')
        return redirect('accounting:invoice_detail', invoice_id=invoice_id)


# =============================================
# AJAX: Get Customer Details
# =============================================
@login_required
def get_customer_details(request, customer_id):
    """
    AJAX endpoint to get customer details for invoice form
    """
    organization = request.user.organization
    
    try:
        customer = Customer.objects.get(
            customer_id=customer_id,
            organization=organization
        )
        
        data = {
            'success': True,
            'customer': {
                'id': customer.customer_id,
                'name': customer.name,
                'tax_id': customer.tax_id or '',
                'address': customer.address or '',
                'phone': customer.phone or '',
                'email': customer.email or '',
                'payment_term_id': customer.payment_term_id,
                'currency_id': customer.currency_id,
            }
        }
        
        return JsonResponse(data)
    
    except Customer.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Customer not found'
        }, status=404)


# =============================================
# IRD Status Dashboard
# =============================================
class IRDStatusDashboardView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Dashboard showing IRD sync status and statistics
    """
    permission_required = 'accounting.view_salesinvoice'
    template_name = 'accounting/ird_dashboard.html'
    
    def get(self, request):
        organization = request.user.organization
        
        # Statistics
        total_invoices = SalesInvoice.objects.filter(
            organization=organization
        ).count()
        
        synced_count = SalesInvoice.objects.filter(
            organization=organization,
            ird_status='synced'
        ).count()
        
        pending_count = SalesInvoice.objects.filter(
            organization=organization,
            status='posted'
        ).filter(
            Q(ird_status__isnull=True) | Q(ird_status='pending')
        ).count()
        
        failed_count = SalesInvoice.objects.filter(
            organization=organization,
            ird_status='failed'
        ).count()
        
        # Recent submissions
        recent_submissions = SalesInvoice.objects.filter(
            organization=organization,
            ird_status='synced'
        ).order_by('-ird_last_submitted_at')[:10]
        
        # Failed submissions
        failed_submissions = SalesInvoice.objects.filter(
            organization=organization,
            ird_status='failed'
        ).order_by('-updated_at')[:10]
        
        context = {
            'total_invoices': total_invoices,
            'synced_count': synced_count,
            'pending_count': pending_count,
            'failed_count': failed_count,
            'sync_rate': (synced_count / total_invoices * 100) if total_invoices > 0 else 0,
            'recent_submissions': recent_submissions,
            'failed_submissions': failed_submissions,
        }
        
        return render(request, self.template_name, context)
