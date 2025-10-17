"""
Advanced Reporting Views - Phase 3 Task 2

Views for generating and displaying financial reports:
- ReportListView: List available reports
- GeneralLedgerView: Generate and display ledger
- TrialBalanceView: Generate trial balance
- ProfitLossView: Generate P&L statement
- BalanceSheetView: Generate balance sheet
- CashFlowView: Generate cash flow
- AccountsReceivableAgingView: Generate A/R aging
- ReportExportView: Handle report exports (PDF/Excel/CSV)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

from accounting.services.report_service import ReportService
from accounting.services.report_export_service import ReportExportService
from accounting.models import Account, JournalType
from usermanagement.models import Organization
from usermanagement.mixins import UserOrganizationMixin

logger = logging.getLogger(__name__)


class ReportListView(UserOrganizationMixin, TemplateView):
    """
    Display list of available reports with filters.
    
    Reports available:
    - General Ledger
    - Trial Balance
    - Profit & Loss
    - Balance Sheet
    - Cash Flow
    - Accounts Receivable Aging
    """
    
    template_name = 'accounting/reports/report_list.html'
    
    def get_context_data(self, **kwargs):
        """Add available reports to context."""
        context = super().get_context_data(**kwargs)
        
        reports = [
            {
                'id': 'general_ledger',
                'name': _('General Ledger'),
                'description': _('View all transactions by account with running balances'),
                'url': 'accounting:report_ledger',
            },
            {
                'id': 'trial_balance',
                'name': _('Trial Balance'),
                'description': _('Verify debits and credits balance for all accounts'),
                'url': 'accounting:report_trial_balance',
            },
            {
                'id': 'profit_loss',
                'name': _('Profit & Loss Statement'),
                'description': _('View revenues, expenses, and net income'),
                'url': 'accounting:report_pl',
            },
            {
                'id': 'balance_sheet',
                'name': _('Balance Sheet'),
                'description': _('View assets, liabilities, and equity'),
                'url': 'accounting:report_bs',
            },
            {
                'id': 'cash_flow',
                'name': _('Cash Flow Statement'),
                'description': _('Analyze cash inflows and outflows'),
                'url': 'accounting:report_cf',
            },
            {
                'id': 'ar_aging',
                'name': _('Accounts Receivable Aging'),
                'description': _('Analyze customer balances by aging period'),
                'url': 'accounting:report_ar_aging',
            },
        ]
        
        context['reports'] = reports
        context['accounts'] = Account.objects.filter(
            organization=self.organization,
            is_active=True
        ).order_by('code')
        
        return context


class GeneralLedgerView(UserOrganizationMixin, View):
    """
    Generate and display General Ledger report.
    
    Supports:
    - Account filtering
    - Date range selection
    - Export to CSV/Excel/PDF
    """
    
    template_name = 'accounting/reports/general_ledger.html'
    
    def get(self, request):
        """Display report form and results."""
        # Get filter parameters
        account_id = request.GET.get('account_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        report_data = None
        
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                # Generate report
                service = ReportService(self.organization)
                service.set_date_range(start_date_obj, end_date_obj)
                report_data = service.generate_general_ledger(
                    account_id=int(account_id) if account_id else None
                )
                
                logger.info(f"Generated General Ledger for {self.organization}")
            except Exception as e:
                logger.exception(f"Error generating ledger: {e}")
                report_data = {'error': str(e)}
        
        context = {
            'report_data': report_data,
            'accounts': Account.objects.filter(
                organization=self.organization,
                is_active=True
            ).order_by('code'),
            'selected_account': account_id,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        return render(request, self.template_name, context)


class TrialBalanceView(UserOrganizationMixin, View):
    """
    Generate and display Trial Balance report.
    """
    
    template_name = 'accounting/reports/trial_balance.html'
    
    def get(self, request):
        """Display trial balance as of date."""
        as_of_date = request.GET.get('as_of_date')
        
        report_data = None
        
        if as_of_date:
            try:
                as_of_date_obj = datetime.strptime(as_of_date, '%Y-%m-%d').date()
                
                service = ReportService(self.organization)
                service.set_date_range(
                    date(as_of_date_obj.year, 1, 1),
                    as_of_date_obj
                )
                report_data = service.generate_trial_balance()
                
                logger.info(f"Generated Trial Balance for {self.organization}")
            except Exception as e:
                logger.exception(f"Error generating trial balance: {e}")
                report_data = {'error': str(e)}
        
        context = {
            'report_data': report_data,
            'as_of_date': as_of_date,
        }
        
        return render(request, self.template_name, context)


class ProfitLossView(UserOrganizationMixin, View):
    """
    Generate and display Profit & Loss statement.
    """
    
    template_name = 'accounting/reports/profit_loss.html'
    
    def get(self, request):
        """Display P&L for period."""
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        report_data = None
        
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                service = ReportService(self.organization)
                service.set_date_range(start_date_obj, end_date_obj)
                report_data = service.generate_profit_loss()
                
                logger.info(f"Generated P&L for {self.organization}")
            except Exception as e:
                logger.exception(f"Error generating P&L: {e}")
                report_data = {'error': str(e)}
        
        context = {
            'report_data': report_data,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        return render(request, self.template_name, context)


class BalanceSheetView(UserOrganizationMixin, View):
    """
    Generate and display Balance Sheet report.
    """
    
    template_name = 'accounting/reports/balance_sheet.html'
    
    def get(self, request):
        """Display balance sheet as of date."""
        as_of_date = request.GET.get('as_of_date')
        
        report_data = None
        
        if as_of_date:
            try:
                as_of_date_obj = datetime.strptime(as_of_date, '%Y-%m-%d').date()
                
                service = ReportService(self.organization)
                service.set_date_range(
                    date(as_of_date_obj.year, 1, 1),
                    as_of_date_obj
                )
                report_data = service.generate_balance_sheet()
                
                logger.info(f"Generated Balance Sheet for {self.organization}")
            except Exception as e:
                logger.exception(f"Error generating balance sheet: {e}")
                report_data = {'error': str(e)}
        
        context = {
            'report_data': report_data,
            'as_of_date': as_of_date,
        }
        
        return render(request, self.template_name, context)


class CashFlowView(UserOrganizationMixin, View):
    """
    Generate and display Cash Flow statement.
    """
    
    template_name = 'accounting/reports/cash_flow.html'
    
    def get(self, request):
        """Display cash flow for period."""
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        report_data = None
        
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                service = ReportService(self.organization)
                service.set_date_range(start_date_obj, end_date_obj)
                report_data = service.generate_cash_flow()
                
                logger.info(f"Generated Cash Flow for {self.organization}")
            except Exception as e:
                logger.exception(f"Error generating cash flow: {e}")
                report_data = {'error': str(e)}
        
        context = {
            'report_data': report_data,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        return render(request, self.template_name, context)


class AccountsReceivableAgingView(UserOrganizationMixin, View):
    """
    Generate and display Accounts Receivable Aging report.
    """
    
    template_name = 'accounting/reports/ar_aging.html'
    
    def get(self, request):
        """Display A/R aging as of date."""
        as_of_date = request.GET.get('as_of_date')
        
        report_data = None
        
        if as_of_date:
            try:
                as_of_date_obj = datetime.strptime(as_of_date, '%Y-%m-%d').date()
                
                service = ReportService(self.organization)
                service.set_date_range(
                    date(as_of_date_obj.year, 1, 1),
                    as_of_date_obj
                )
                report_data = service.generate_accounts_receivable_aging()
                
                logger.info(f"Generated A/R Aging for {self.organization}")
            except Exception as e:
                logger.exception(f"Error generating A/R aging: {e}")
                report_data = {'error': str(e)}
        
        context = {
            'report_data': report_data,
            'as_of_date': as_of_date,
        }
        
        return render(request, self.template_name, context)


class ReportExportView(UserOrganizationMixin, View):
    """
    Handle report export to CSV/Excel/PDF formats.
    
    Request parameters:
    - report_type: Type of report
    - export_format: csv, excel, pdf
    - [other parameters specific to report type]
    """
    
    def post(self, request):
        """Export report in requested format."""
        report_type = request.POST.get('report_type')
        export_format = request.POST.get('export_format', 'csv')
        
        try:
            # Generate report data based on type
            service = ReportService(self.organization)
            
            # Parse dates from POST data
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            account_id = request.POST.get('account_id')
            
            if start_date and end_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                service.set_date_range(start_date_obj, end_date_obj)
            
            # Generate report
            if report_type == 'general_ledger':
                report_data = service.generate_general_ledger(
                    account_id=int(account_id) if account_id else None
                )
            elif report_type == 'trial_balance':
                report_data = service.generate_trial_balance()
            elif report_type == 'profit_loss':
                report_data = service.generate_profit_loss()
            elif report_type == 'balance_sheet':
                report_data = service.generate_balance_sheet()
            elif report_type == 'cash_flow':
                report_data = service.generate_cash_flow()
            elif report_type == 'ar_aging':
                report_data = service.generate_accounts_receivable_aging()
            else:
                return JsonResponse({'error': 'Invalid report type'}, status=400)
            
            # Export to requested format
            if export_format == 'csv':
                file_buffer, filename = ReportExportService.to_csv(report_data)
                content_type = 'text/csv'
            elif export_format == 'excel':
                file_buffer, filename = ReportExportService.to_excel(report_data)
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif export_format == 'pdf':
                file_buffer, filename = ReportExportService.to_pdf(report_data)
                content_type = 'application/pdf'
            else:
                return JsonResponse({'error': 'Invalid export format'}, status=400)
            
            # Create response
            response = HttpResponse(file_buffer.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"Exported {report_type} as {export_format} for {self.organization}")
            return response
        
        except Exception as e:
            logger.exception(f"Error exporting report: {e}")
            return JsonResponse({'error': str(e)}, status=500)
