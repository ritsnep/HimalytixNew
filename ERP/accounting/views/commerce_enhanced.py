from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.forms import inlineformset_factory
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from urllib.parse import urlencode
import json
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
from django.views.generic import ListView
from django.http import JsonResponse

from accounting.forms import (
    APPaymentForm,
    APPaymentLineForm,
    CustomerForm,
    VendorForm,
)
from accounting.mixins import PermissionRequiredMixin, UserOrganizationMixin
from accounting.models import APPayment, APPaymentLine, Currency, Customer, Vendor, PaymentTerm
from usermanagement.utils import PermissionUtils
from accounting.views.base_views import SmartListMixin
from accounting.services.app_payment_service import APPaymentService

APPaymentLineFormSet = inlineformset_factory(
    APPayment,
    APPaymentLine,
    form=APPaymentLineForm,
    extra=1,
    can_delete=True,
)


class EnhancedAPPaymentListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    """
    Enhanced AP Payment List View with comprehensive filtering and bulk operations.
    """
    model = APPayment
    template_name = "accounting/enhanced_ap_payment_list.html"
    context_object_name = "payments"
    permission_required = ("accounting", "appayment", "view")
    paginate_by = 25

    def get_queryset(self):
        organization = self.get_organization()
        if not organization:
            return APPayment.objects.none()
        
        queryset = APPayment.objects.filter(organization=organization).select_related("vendor", "currency")
        
        # Apply filters
        status_filter = self.request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Search functionality
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(payment_number__icontains=search_query) |
                Q(vendor__display_name__icontains=search_query) |
                Q(vendor__code__icontains=search_query)
            )
        
        # Date range filters
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)
        
        # Amount range filters
        amount_min = self.request.GET.get('amount_min', '')
        amount_max = self.request.GET.get('amount_max', '')
        if amount_min:
            try:
                queryset = queryset.filter(amount__gte=Decimal(amount_min))
            except:
                pass
        if amount_max:
            try:
                queryset = queryset.filter(amount__lte=Decimal(amount_max))
            except:
                pass
        
        # Vendor filter
        vendor_filter = self.request.GET.get('vendor', '')
        if vendor_filter:
            queryset = queryset.filter(vendor_id=vendor_filter)
        
        # Sort ordering
        sort_by = self.request.GET.get('sort_by', '-payment_date')
        sort_fields = ['payment_date', 'payment_number', 'vendor__display_name', 'amount', 'status']
        if sort_by.replace('-', '') in sort_fields:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-payment_date')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        # Add filter options
        context["status_choices"] = APPayment.STATUS_CHOICES
        context["vendors"] = Vendor.objects.filter(organization=organization, is_active=True).order_by('display_name')
        context["currencies"] = Currency.objects.filter(is_active=True)
        
        # Get summary statistics
        qs = self.get_queryset()
        summary = qs.aggregate(
            total_count=Count('payment_id'),
            total_amount=Sum('amount'),
            draft_count=Count('payment_id', filter=Q(status='draft')),
            approved_count=Count('payment_id', filter=Q(status='approved')),
            executed_count=Count('payment_id', filter=Q(status='executed')),
            reconciled_count=Count('payment_id', filter=Q(status='reconciled')),
            cancelled_count=Count('payment_id', filter=Q(status='cancelled')),
        )
        
        context["summary"] = summary
        
        # Add current filters to context for preserving state
        context["current_filters"] = {
            'status': self.request.GET.get('status', ''),
            'search': self.request.GET.get('search', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'amount_min': self.request.GET.get('amount_min', ''),
            'amount_max': self.request.GET.get('amount_max', ''),
            'vendor': self.request.GET.get('vendor', ''),
            'sort_by': self.request.GET.get('sort_by', '-payment_date'),
        }
        
        context["create_url"] = reverse("accounting:ap_payment_create")
        context["create_button_text"] = "New AP Payment"
        context.setdefault("page_title", "AP Payments")
        
        return context


class APPaymentBulkActionView(PermissionRequiredMixin, UserOrganizationMixin, View):
    """
    Handles bulk actions on AP payments (approve, execute, reconcile, cancel).
    """
    permission_required = ("accounting", "appayment", "change")
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            action = data.get('action')
            payment_ids = data.get('payment_ids', [])
            notes = data.get('notes', '')
            
            if not payment_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'No payment IDs provided'
                })
            
            organization = self.get_organization()
            if not organization:
                return JsonResponse({
                    'success': False,
                    'error': 'Organization not found'
                })
            
            # Validate payments belong to organization
            valid_payments = APPayment.objects.filter(
                payment_id__in=payment_ids,
                organization=organization
            )
            
            if valid_payments.count() != len(payment_ids):
                return JsonResponse({
                    'success': False,
                    'error': 'Some payment IDs are invalid or belong to different organization'
                })
            
            # Initialize service
            service = APPaymentService(request.user)
            
            # Get journal type for execute operations
            journal_type = None
            if action in ['execute', 'bulk_execute']:
                # Get a default journal type - you may want to make this configurable
                from accounting.models import JournalType
                journal_type = JournalType.objects.filter(
                    organization=organization,
                    is_active=True
                ).first()
                
                if not journal_type:
                    return JsonResponse({
                        'success': False,
                        'error': 'No active journal types found for payment execution'
                    })
            
            # Perform bulk action based on operation
            result = None
            
            if action == 'approve':
                result = service.bulk_approve_payments(payment_ids, notes=notes)
            elif action == 'execute':
                result = service.bulk_execute_payments(payment_ids, journal_type, notes=notes)
            elif action == 'reconcile':
                result = service.bulk_reconcile_payments(payment_ids, notes=notes)
            elif action == 'cancel':
                result = service.bulk_cancel_payments(payment_ids, reason=notes)
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown action: {action}'
                })
            
            # Prepare response
            response_data = {
                'success': True,
                'action': action,
                'total_count': result.total_count,
                'successful_count': len(result.successful),
                'failed_count': len(result.failed),
                'successful_payments': [
                    {
                        'id': payment.payment_id,
                        'payment_number': payment.payment_number,
                        'status': payment.status
                    }
                    for payment in result.successful
                ],
                'failed_payments': result.failed
            }
            
            # Add appropriate success message
            if result.failed:
                messages.warning(request, f"{action.title()} completed with some errors. Check results for details.")
            else:
                messages.success(request, f"Successfully {action}d {len(result.successful)} payment(s).")
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Operation failed: {str(e)}'
            })


@method_decorator(csrf_exempt, name='dispatch')
class APPaymentStatusUpdateView(PermissionRequiredMixin, UserOrganizationMixin, View):
    """
    AJAX endpoint for updating individual payment status.
    """
    permission_required = ("accounting", "appayment", "change")
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            payment_id = data.get('payment_id')
            action = data.get('action')
            notes = data.get('notes', '')
            
            organization = self.get_organization()
            if not organization:
                return JsonResponse({
                    'success': False,
                    'error': 'Organization not found'
                })
            
            payment = get_object_or_404(
                APPayment, 
                payment_id=payment_id, 
                organization=organization
            )
            
            service = APPaymentService(request.user)
            
            if action == 'approve':
                payment = service.approve_payment(payment, notes=notes)
                success_message = f"Payment {payment.payment_number} approved successfully"
            elif action == 'execute':
                # Get journal type
                from accounting.models import JournalType
                journal_type = JournalType.objects.filter(
                    organization=organization,
                    is_active=True
                ).first()
                
                if not journal_type:
                    return JsonResponse({
                        'success': False,
                        'error': 'No active journal types found for payment execution'
                    })
                
                payment = service.execute_payment(payment, journal_type)
                success_message = f"Payment {payment.payment_number} executed successfully"
            elif action == 'reconcile':
                payment = service.reconcile_payment(payment, notes=notes)
                success_message = f"Payment {payment.payment_number} reconciled successfully"
            elif action == 'cancel':
                payment = service.cancel_payment(payment, reason=notes)
                success_message = f"Payment {payment.payment_number} cancelled successfully"
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Unknown action: {action}'
                })
            
            return JsonResponse({
                'success': True,
                'message': success_message,
                'payment': {
                    'id': payment.payment_id,
                    'payment_number': payment.payment_number,
                    'status': payment.status,
                    'updated_at': payment.updated_at.isoformat() if payment.updated_at else None
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class APPaymentSummaryAjaxView(PermissionRequiredMixin, UserOrganizationMixin, View):
    """
    AJAX view to get payment summary for real-time updates.
    """
    permission_required = ("accounting", "appayment", "view")
    
    @require_http_methods(["GET"])
    def get(self, request):
        organization_id = request.GET.get('organization_id')
        
        if not organization_id:
            return JsonResponse({'error': 'Organization ID required'}, status=400)
        
        try:
            from usermanagement.models import Organization
            from django.db.models import Count, Sum, Q
            organization = Organization.objects.get(id=organization_id)
            
            # Get summary statistics similar to the list view
            qs = APPayment.objects.filter(organization=organization)
            summary = qs.aggregate(
                total_count=Count('payment_id'),
                total_amount=Sum('amount'),
                draft_count=Count('payment_id', filter=Q(status='draft')),
                approved_count=Count('payment_id', filter=Q(status='approved')),
                executed_count=Count('payment_id', filter=Q(status='executed')),
                reconciled_count=Count('payment_id', filter=Q(status='reconciled')),
                cancelled_count=Count('payment_id', filter=Q(status='cancelled')),
            )
            
            return JsonResponse({
                'success': True,
                'summary': summary
            })
            
        except Organization.DoesNotExist:
            return JsonResponse({'error': 'Organization not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


