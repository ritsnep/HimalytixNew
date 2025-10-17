"""
Views for Scheduled Tasks Management - Phase 3 Task 4

Views for:
- Period closing
- Recurring entry management
- Scheduled report configuration
- Task monitoring and history
"""

from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
import logging
from decimal import Decimal
from datetime import datetime, timedelta

# Try to import Celery, but make it optional
try:
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    AsyncResult = None

from accounting.models import (
    AccountingPeriod, 
    Organization, 
    Journal, 
    RecurringJournal as RecurringEntry,
    ScheduledReport,
    ScheduledTaskExecution
)
from accounting.mixins import UserOrganizationMixin
from accounting.celery_tasks import (
    close_accounting_period,
    post_recurring_entries,
    generate_scheduled_reports,
    validate_period_entries
)
from accounting.forms import (
    AccountingPeriodCloseForm,
    RecurringEntryForm,
    ScheduledReportForm
)

logger = logging.getLogger(__name__)


class PeriodClosingListView(LoginRequiredMixin, UserOrganizationMixin, ListView):
    """
    Display accounting periods with closing status and history.
    
    Provides:
    - List of periods with status (Open/Closed)
    - Closing history
    - Quick close action
    - Validation results
    """
    
    model = AccountingPeriod
    template_name = 'accounting/scheduled_tasks/period_list.html'
    context_object_name = 'periods'
    paginate_by = 20
    
    def get_queryset(self):
        """Get periods for organization."""
        org = self.get_user_organization()
        return AccountingPeriod.objects.filter(
            organization=org
        ).order_by('-end_date')
    
    def get_context_data(self, **kwargs):
        """Add statistics to context."""
        context = super().get_context_data(**kwargs)
        org = self.get_user_organization()
        
        # Count open/closed periods
        all_periods = AccountingPeriod.objects.filter(organization=org)
        context['total_periods'] = all_periods.count()
        context['open_periods'] = all_periods.filter(is_closed=False).count()
        context['closed_periods'] = all_periods.filter(is_closed=True).count()
        
        # Get current period
        today = timezone.now().date()
        context['current_period'] = all_periods.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()
        
        return context


class PeriodClosingDetailView(LoginRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Display period details with validation and closing options.
    
    Provides:
    - Period summary
    - Journal count and status breakdown
    - Validation results
    - Close button with confirmation
    """
    
    model = AccountingPeriod
    template_name = 'accounting/scheduled_tasks/period_detail.html'
    context_object_name = 'period'
    
    def get_queryset(self):
        """Get periods for organization."""
        org = self.get_user_organization()
        return AccountingPeriod.objects.filter(organization=org)
    
    def get_context_data(self, **kwargs):
        """Add validation data to context."""
        context = super().get_context_data(**kwargs)
        period = self.get_object()
        org = self.get_user_organization()
        
        # Get journals in period
        journals = Journal.objects.filter(
            organization=org,
            date__gte=period.start_date,
            date__lte=period.end_date
        )
        
        context['total_journals'] = journals.count()
        context['posted_journals'] = journals.filter(status='Posted').count()
        context['draft_journals'] = journals.filter(status='Draft').count()
        context['submitted_journals'] = journals.filter(status='Submitted').count()
        
        # Check for unbalanced journals
        unbalanced = []
        for journal in journals:
            debit_total = sum(
                line.debit or Decimal('0')
                for line in journal.journalline_set.all()
            )
            credit_total = sum(
                line.credit or Decimal('0')
                for line in journal.journalline_set.all()
            )
            
            if debit_total != credit_total:
                unbalanced.append({
                    'journal': journal,
                    'difference': debit_total - credit_total
                })
        
        context['unbalanced_journals'] = unbalanced
        context['can_close'] = (
            not period.is_closed and
            journals.filter(status__in=['Draft', 'Submitted']).count() == 0 and
            len(unbalanced) == 0
        )
        
        return context


class PeriodClosingView(LoginRequiredMixin, UserOrganizationMixin, View):
    """
    Handle period closing action.
    
    Provides:
    - Validation before closing
    - Async task scheduling
    - Result tracking
    """
    
    http_method_names = ['post']
    
    def post(self, request, pk):
        """Close accounting period."""
        org = self.get_user_organization()
        period = get_object_or_404(
            AccountingPeriod,
            pk=pk,
            organization=org
        )
        
        # Validate period can be closed
        if period.is_closed:
            return JsonResponse({
                'status': 'error',
                'message': 'Period already closed'
            }, status=400)
        
        unposted = Journal.objects.filter(
            organization=org,
            date__gte=period.start_date,
            date__lte=period.end_date,
            status__in=['Draft', 'Submitted']
        ).count()
        
        if unposted > 0:
            return JsonResponse({
                'status': 'error',
                'message': f'{unposted} unposted journals must be posted first'
            }, status=400)
        
        try:
            # Schedule Celery task
            task = close_accounting_period.delay(period.pk)
            
            logger.info(f'Period {period.name} closing scheduled: {task.id}')
            
            return JsonResponse({
                'status': 'success',
                'message': f'Closing {period.name}...',
                'task_id': task.id
            })
        except Exception as e:
            logger.error(f'Error scheduling period close: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class RecurringEntryListView(LoginRequiredMixin, UserOrganizationMixin, ListView):
    """
    Display recurring journal entry templates.
    
    Provides:
    - List of recurring entries
    - Status and frequency info
    - Last/next posting dates
    - Edit/delete actions
    """
    
    model = RecurringEntry
    template_name = 'accounting/scheduled_tasks/recurring_list.html'
    context_object_name = 'recurring_entries'
    paginate_by = 20
    
    def get_queryset(self):
        """Get recurring entries for organization."""
        org = self.get_user_organization()
        return RecurringEntry.objects.filter(
            organization=org
        ).order_by('code')
    
    def get_context_data(self, **kwargs):
        """Add statistics to context."""
        context = super().get_context_data(**kwargs)
        org = self.get_user_organization()
        
        all_recurring = RecurringEntry.objects.filter(organization=org)
        context['total_recurring'] = all_recurring.count()
        context['active_recurring'] = all_recurring.filter(is_active=True).count()
        context['inactive_recurring'] = all_recurring.filter(is_active=False).count()
        
        # Due today
        today = timezone.now().date()
        context['due_today'] = all_recurring.filter(
            is_active=True,
            next_posting_date__lte=today
        ).count()
        
        return context


class RecurringEntryCreateView(LoginRequiredMixin, UserOrganizationMixin, CreateView):
    """
    Create recurring journal entry template.
    
    Provides:
    - Template form with accounts and amounts
    - Frequency selection
    - Start date configuration
    - Line item editor
    """
    
    model = RecurringEntry
    form_class = RecurringEntryForm
    template_name = 'accounting/scheduled_tasks/recurring_form.html'
    success_url = reverse_lazy('accounting:recurring_list')
    
    def form_valid(self, form):
        """Save recurring entry for organization."""
        org = self.get_user_organization()
        form.instance.organization = org
        
        logger.info(f'Creating recurring entry: {form.instance.code}')
        
        return super().form_valid(form)


class RecurringEntryUpdateView(LoginRequiredMixin, UserOrganizationMixin, UpdateView):
    """Update recurring journal entry."""
    
    model = RecurringEntry
    form_class = RecurringEntryForm
    template_name = 'accounting/scheduled_tasks/recurring_form.html'
    success_url = reverse_lazy('accounting:recurring_list')
    
    def get_queryset(self):
        """Get recurring entries for organization."""
        org = self.get_user_organization()
        return RecurringEntry.objects.filter(organization=org)


class RecurringEntryDeleteView(LoginRequiredMixin, UserOrganizationMixin, DeleteView):
    """Delete recurring journal entry."""
    
    model = RecurringEntry
    template_name = 'accounting/scheduled_tasks/recurring_confirm_delete.html'
    success_url = reverse_lazy('accounting:recurring_list')
    
    def get_queryset(self):
        """Get recurring entries for organization."""
        org = self.get_user_organization()
        return RecurringEntry.objects.filter(organization=org)


class ScheduledReportListView(LoginRequiredMixin, UserOrganizationMixin, ListView):
    """
    Display scheduled report configurations.
    
    Provides:
    - List of configured reports
    - Schedule details
    - Last run information
    - Edit/delete actions
    """
    
    model = ScheduledReport
    template_name = 'accounting/scheduled_tasks/report_list.html'
    context_object_name = 'scheduled_reports'
    paginate_by = 20
    
    def get_queryset(self):
        """Get scheduled reports for organization."""
        org = self.get_user_organization()
        return ScheduledReport.objects.filter(
            organization=org
        ).order_by('name')


class ScheduledReportCreateView(LoginRequiredMixin, UserOrganizationMixin, CreateView):
    """
    Create scheduled report configuration.
    
    Provides:
    - Report type selection
    - Schedule configuration (daily, weekly, monthly)
    - Recipient list
    - Format selection
    """
    
    model = ScheduledReport
    form_class = ScheduledReportForm
    template_name = 'accounting/scheduled_tasks/report_form.html'
    success_url = reverse_lazy('accounting:scheduled_report_list')
    
    def form_valid(self, form):
        """Save scheduled report for organization."""
        org = self.get_user_organization()
        form.instance.organization = org
        
        logger.info(f'Creating scheduled report: {form.instance.name}')
        
        return super().form_valid(form)


class ScheduledReportUpdateView(LoginRequiredMixin, UserOrganizationMixin, UpdateView):
    """Update scheduled report configuration."""
    
    model = ScheduledReport
    form_class = ScheduledReportForm
    template_name = 'accounting/scheduled_tasks/report_form.html'
    success_url = reverse_lazy('accounting:scheduled_report_list')
    
    def get_queryset(self):
        """Get scheduled reports for organization."""
        org = self.get_user_organization()
        return ScheduledReport.objects.filter(organization=org)


class ScheduledReportDeleteView(LoginRequiredMixin, UserOrganizationMixin, DeleteView):
    """Delete scheduled report configuration."""
    
    model = ScheduledReport
    template_name = 'accounting/scheduled_tasks/report_confirm_delete.html'
    success_url = reverse_lazy('accounting:scheduled_report_list')
    
    def get_queryset(self):
        """Get scheduled reports for organization."""
        org = self.get_user_organization()
        return ScheduledReport.objects.filter(organization=org)


class TaskMonitorView(LoginRequiredMixin, UserOrganizationMixin, View):
    """
    Monitor Celery task execution.
    
    Provides:
    - Task status
    - Progress tracking
    - Result display
    - Error reporting
    """
    
    http_method_names = ['get']
    
    def get(self, request, task_id):
        """Get task status."""
        try:
            task = AsyncResult(task_id)
            
            response = {
                'task_id': task_id,
                'status': task.status,
                'result': task.result if task.status == 'SUCCESS' else None,
                'error': str(task.info) if task.status == 'FAILURE' else None
            }
            
            return JsonResponse(response)
        except Exception as e:
            logger.error(f'Error getting task status: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class TaskHistoryView(LoginRequiredMixin, UserOrganizationMixin, ListView):
    """
    Display history of scheduled task executions.
    
    Provides:
    - Task execution log
    - Status breakdown
    - Error tracking
    - Performance metrics
    """
    
    model = ScheduledTaskExecution
    template_name = 'accounting/scheduled_tasks/task_history.html'
    context_object_name = 'executions'
    paginate_by = 50
    
    def get_queryset(self):
        """Get task executions for organization."""
        org = self.get_user_organization()
        return ScheduledTaskExecution.objects.filter(
            organization=org
        ).order_by('-executed_at')
    
    def get_context_data(self, **kwargs):
        """Add statistics to context."""
        context = super().get_context_data(**kwargs)
        org = self.get_user_organization()
        
        executions = ScheduledTaskExecution.objects.filter(organization=org)
        context['total_executions'] = executions.count()
        context['successful'] = executions.filter(status='Success').count()
        context['failed'] = executions.filter(status='Failed').count()
        context['pending'] = executions.filter(status='Pending').count()
        
        # Last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        context['recent_executions'] = executions.filter(
            executed_at__gte=yesterday
        ).count()
        
        return context


class PostRecurringEntriesView(LoginRequiredMixin, UserOrganizationMixin, View):
    """
    Manually trigger recurring entry posting.
    
    Provides:
    - Immediate posting of due recurring entries
    - Result summary
    - Error handling
    """
    
    http_method_names = ['post']
    
    def post(self, request):
        """Post due recurring entries."""
        org = self.get_user_organization()
        
        try:
            task = post_recurring_entries.delay(org.pk)
            
            logger.info(f'Recurring entries posting scheduled: {task.id}')
            
            return JsonResponse({
                'status': 'success',
                'message': 'Posting recurring entries...',
                'task_id': task.id
            })
        except Exception as e:
            logger.error(f'Error scheduling recurring entries: {str(e)}')
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
