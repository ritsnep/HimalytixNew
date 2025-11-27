import json
import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Q, Sum, Count
from django.http import HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import translation
from django.views import View
from django.views.decorators.http import require_POST  # Added this line
from django.views.generic import TemplateView
from usermanagement.forms import DasonLoginForm
from usermanagement.utils import permission_required  # Added this line

from api.authentication import issue_streamlit_token
from utils.maintenance import get_maintenance_state, serialize_state

from accounting.models import (
    ChartOfAccount, Journal, JournalLine, GeneralLedger,
    FiscalYear, AccountingPeriod, AccountType
)
from usermanagement.models import Organization

# Dashboard
# @login_required
# class DashboardView(View):
#     def get(self, request):
#         return render(request, "dashboard.html")

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        organization = user.get_active_organization()
        
        if not organization:
            context['error'] = 'No active organization found. Please select an organization.'
            return context
        
        # Get current fiscal year and period
        current_fiscal_year = FiscalYear.objects.filter(
            organization_id=organization.id,
            is_current=True
        ).first()
        
        current_period = None
        if current_fiscal_year:
            current_period = AccountingPeriod.objects.filter(
                fiscal_year_id=current_fiscal_year.id,
                is_current=True
            ).first()
        
        # Get account balances
        account_balances = self.get_account_balances(organization, current_period)
        
        # Get recent journals
        recent_journals = Journal.objects.filter(
            organization_id=organization.id
        ).select_related(
            'organization',
            'journal_type',
            'period',
            'period__fiscal_year',
            'created_by',
            'approved_by',
            'posted_by'
        ).prefetch_related(
            'journalline_set__account'
        ).order_by('-journal_date', '-created_at')[:10]
        
        # Get financial summary
        financial_summary = self.get_financial_summary(organization, current_period)
        
        context.update({
            'organization': organization,
            'current_fiscal_year': current_fiscal_year,
            'current_period': current_period,
            'account_balances': account_balances,
            'recent_journals': recent_journals,
            'financial_summary': financial_summary,
        })
        
        return context
    
    def get_account_balances(self, organization, period):
        """Get account balances for the dashboard"""
        if not period:
            return []
        
        # Get account balances from GeneralLedger
        balances = GeneralLedger.objects.filter(
            organization_id=organization.id,
            period=period
        ).select_related(
            'account',
            'organization'
        ).values('account__account_name', 'account__account_code').annotate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        ).order_by('account__account_code')[:10]  # Top 10 accounts
        
        for balance in balances:
            balance['net_balance'] = (balance['total_debit'] or Decimal('0')) - (balance['total_credit'] or Decimal('0'))
        
        return balances
    
    def get_financial_summary(self, organization, period):
        """Get key financial metrics"""
        if not period:
            return {}
        
        # Use a single aggregated query for journal stats instead of multiple count() queries
        journal_stats = Journal.objects.filter(
            organization=organization,
            period=period
        ).aggregate(
            total=Sum('id') / Sum('id'),  # Trick to get count as 1 or 0
            total_journals=Count('id'),
            posted_journals=Count('id', filter=Q(status='posted')),
            draft_journals=Count('id', filter=Q(status='draft')),
        )
        
        # Get account type aggregations in a single query
        account_balances = GeneralLedger.objects.filter(
            organization_id=organization.id,
            period=period
        ).select_related('account__account_type').values(
            'account__account_type__nature'
        ).annotate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount')
        )
        
        # Calculate totals from aggregated data
        total_assets = Decimal('0')
        total_liabilities = Decimal('0')
        total_equity = Decimal('0')
        
        for balance in account_balances:
            net_balance = (balance['total_debit'] or Decimal('0')) - (balance['total_credit'] or Decimal('0'))
            nature = balance['account__account_type__nature']
            if nature == 'asset':
                total_assets += net_balance
            elif nature == 'liability':
                total_liabilities += net_balance
            elif nature == 'equity':
                total_equity += net_balance
        
        return {
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'total_journals': journal_stats['total_journals'] or 0,
            'posted_journals': journal_stats['posted_journals'] or 0,
            'draft_journals': journal_stats['draft_journals'] or 0,
        }

class Settings(LoginRequiredMixin, View):
    template_name = "settings.html"

    def __init__(self, *args):
        super(Settings, self).__init__(*args)

    def get(self, request):
        return render(request, self.template_name)

class CustomLoginView(LoginView):
    template_name = "account/login.html"
    authentication_form = DasonLoginForm
    success_url = reverse_lazy("dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_url = self.request.GET.get('next') or self.request.POST.get('next') or '/'
        print(f"[DEBUG] LoginView next_url: {next_url}")  # Debug print
        context['next'] = next_url
        return context

    def get_success_url(self):
        """Always return the main dashboard as the post-login destination."""
        return str(self.success_url)


def set_language(request):
    """Set the UI language (session + cookie) and redirect back."""
    lang = request.GET.get("lang") or request.POST.get("lang") or "en"
    # Normalize like 'en-us' -> 'en'
    lang_short = lang.split('-')[0]
    request.session[settings.LANGUAGE_COOKIE_NAME] = lang_short
    request.session["django_language"] = lang_short
    try:
        translation.activate(lang_short)
    except Exception:
        pass
    response = HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_short)
    return response


def set_region(request):
    """Set the region preference (for formatting) and redirect back."""
    region = request.GET.get("region") or request.POST.get("region") or "US"
    request.session["region"] = region.upper()
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


def maintenance_status(request):
    """Lightweight JSON status for maintenance banner / client polling."""
    state = serialize_state()
    snapshot = getattr(request, "maintenance_snapshot", None)
    if snapshot:
        state["snapshot"] = snapshot
    return JsonResponse(state)


def maintenance_stream(request):
    """Simple SSE stream that emits state changes to connected clients."""
    # Check if maintenance mode is active first
    state = get_maintenance_state()
    if not state.get('active', False):
        # If not in maintenance mode, send one message and close connection
        def quick_response():
            yield f"data: {{\"active\": false}}\n\n"
        response = StreamingHttpResponse(quick_response(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        return response
    
    # Only run the loop if maintenance mode is actually active
    max_messages = getattr(settings, "MAINTENANCE_STREAM_MAX_MESSAGES", 30)  # Reduced from 120 to 30
    interval = getattr(settings, "MAINTENANCE_STREAM_INTERVAL", 2)

    def event_stream():
        last_payload = None
        for _ in range(max_messages):
            payload = serialize_state()
            # Exit early if maintenance mode is deactivated
            if not payload.get('active', False):
                yield f"data: {json.dumps(payload)}\n\n"
                break
            
            data = json.dumps(payload)
            if data != last_payload:
                yield f"data: {data}\n\n"
                last_payload = data
            time.sleep(interval)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    return response


@login_required
@require_POST
@permission_required('dashboard.access_streamlit')
def v2_login_redirect(request):
    """Issue a short-lived token and redirect to /V2 with token as query param.

    This assumes the reverse proxy maps /V2 to the Streamlit app. Token is removed
    by the Streamlit app immediately after bootstrap.
    """
    tenant_id = getattr(getattr(request, 'tenant', None), 'id', None) or request.session.get('active_tenant')
    token = issue_streamlit_token(request.user, tenant_id=tenant_id)
    return redirect(f"/V2?st={token}")
