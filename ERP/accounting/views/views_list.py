from accounting.models import (
    AccountType, FiscalYear, GeneralLedger, Journal,  JournalLine, JournalType, ChartOfAccount, 
    AccountingPeriod, TaxCode, Department, Project, CostCenter,
    VoucherModeConfig, VoucherModeDefault, Currency, CurrencyExchangeRate, TaxAuthority, TaxType
)
from accounting.forms import AccountTypeForm, FiscalYearForm, JournalForm, JournalLineForm, JournalLineFormSet, VoucherModeConfigForm, VoucherModeDefaultForm, VoucherUDFConfigForm, AccountingPeriodForm, JournalTypeForm, ChartOfAccountForm, CostCenterForm, TaxTypeForm, TaxAuthorityForm, CurrencyForm, CurrencyExchangeRateForm, ProjectForm, DepartmentForm
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounting.views.views_mixins import PermissionRequiredMixin
from accounting.views.base_views import BaseListView, SmartListView
from django.urls import reverse
from usermanagement.utils import PermissionUtils  # Add this import for PermissionUtils
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils.decorators import method_decorator
from utils.htmx import require_htmx
from django.db import models
from django.db.models import Sum
from accounting.models import VoucherUDFConfig
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required

# @login_required
def general_journal_advanced_entry(request):
    """Render the advanced journal entry page with config and schema."""
    from accounting.models import VoucherModeConfig, JournalType
    from django.utils import timezone
    # Find the default or first active config for general journal
    organization = request.user.get_active_organization()
    journal_type = JournalType.objects.filter(organization=organization, code__iexact='GENERAL').first()
    config = None
    if journal_type:
        config = VoucherModeConfig.objects.filter(journal_type=journal_type, is_active=True, archived_at__isnull=True).order_by('-is_default', 'pk').first()
    if not config:
        config = VoucherModeConfig.objects.filter(organization=organization, is_active=True, archived_at__isnull=True).order_by('-is_default', 'pk').first()
    schema = config.resolve_ui() if config else None
    context = {
        'config': config,
        'schema': schema,
        'page_title': 'Advanced Journal Entry',
        'status': 'Draft',
        'journal_number': '',
        'total_debit': '0.00',
        'total_credit': '0.00',
        'balance_text': 'Balanced',
        'balance_class': 'balance-balanced',
    }
    if not config or not schema:
        context['error'] = 'No active general journal configuration found.'
    return render(request, "accounting/general_journal_advanced_entry.html", context)


class FiscalYearListView(SmartListView):
    model = FiscalYear
    template_name = 'accounting/fiscal_year_list.html'
    context_object_name = 'fiscal_years'
    permission_required = ('accounting', 'fiscalyear', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:fiscal_year_create')
        context['create_button_text'] = 'New Fiscal Year'
        return context

class CostCenterListView(SmartListView):
    model = CostCenter
    template_name = 'accounting/costcenter_list.html'
    context_object_name = 'cost_centers'
    permission_required = ('accounting', 'costcenter', 'view')

    def get_queryset(self):
        today = timezone.now().date()
        return super().get_queryset().filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=today),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:costcenter_create')
        context['create_button_text'] = 'New Cost Center'
        return context

class DepartmentListView(SmartListView):
    model = Department
    template_name = 'accounting/department_list.html'
    context_object_name = 'departments'
    permission_required = ('accounting', 'department', 'view')

    def get_queryset(self):
        today = timezone.now().date()
        return super().get_queryset().filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=today),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:department_create')
        context['create_button_text'] = 'New Department'
        return context

class JournalListView(BaseListView):
    """Main journal listing view with filtering and permissions."""
    model = Journal
    template_name = 'accounting/journal_list.html'
    context_object_name = 'journals'
    permission_required = ('accounting', 'journal', 'view')

    def get_paginate_by(self, queryset):
        return self.request.GET.get('rows', 20)

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'journal_type', 'period', 'created_by', 'posted_by'
        )
        # Don't prefetch lines on list view - only fetch when needed for detail view
        # This significantly improves performance on large datasets

        # Apply filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        account_filter = self.request.GET.get('account')
        status_filter = self.request.GET.get('status')

        if start_date:
            queryset = queryset.filter(journal_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(journal_date__lte=end_date)
        if account_filter:
            queryset = queryset.filter(lines__account_id=account_filter).distinct()
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Apply sorting
        sort_by = self.request.GET.get('sort_by', '-journal_date')
        order = self.request.GET.get('order', 'desc')
        
        if order.lower() == 'desc':
            sort_by = f"-{sort_by.lstrip('-')}"
        else:
            sort_by = sort_by.lstrip('-')

        if 'total_debit' in sort_by or 'total_credit' in sort_by:
            queryset = queryset.annotate(
                calculated_debit=Sum('lines__debit_amount'),
                calculated_credit=Sum('lines__credit_amount')
            )
            if 'total_debit' in sort_by:
                sort_by = sort_by.replace('total_debit', 'calculated_debit')
            if 'total_credit' in sort_by:
                sort_by = sort_by.replace('total_credit', 'calculated_credit')

        return queryset.order_by(sort_by, '-journal_number')
    
    def get_template_names(self):
        if self.request.htmx:
            return ["accounting/partials/journal_list_partial.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()

        current_fiscal_year = FiscalYear.objects.filter(
            organization=organization,
            is_current=True
        ).first()

        if current_fiscal_year:
            context['default_start_date'] = current_fiscal_year.start_date.isoformat()
            context['default_end_date'] = current_fiscal_year.end_date.isoformat()
        
        accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).order_by('account_code')
        
        journal_types = JournalType.objects.filter(
            organization_id=organization.id,
            is_active=True
        )
        config = VoucherModeConfig.objects.filter(organization=organization, is_active=True, archived_at__isnull=True).order_by('-is_default', 'pk').first()
        
        selected_account_text = ''
        account_filter_id = self.request.GET.get('account')
        if account_filter_id:
            try:
                selected_account = ChartOfAccount.objects.get(pk=account_filter_id, organization_id=organization.id)
                selected_account_text = f"{selected_account.account_code} - {selected_account.account_name}"
            except ChartOfAccount.DoesNotExist:
                pass

        context.update({
            'accounts': accounts,
            'journal_types': journal_types,
            'config': config,
            'selected_account_text': selected_account_text,
        })
        return context

class VoucherModeConfigListView(SmartListView):
    model = VoucherModeConfig
    template_name = 'forms_designer/voucher_config_list.html'
    context_object_name = 'configs'
    permission_required = ('accounting', 'vouchermodeconfig', 'view')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:voucher_config_create')
        context['create_button_text'] = 'New Voucher Mode Config'
        return context

class VoucherModeConfigDetailView(PermissionRequiredMixin, LoginRequiredMixin, DetailView):
    model = VoucherModeConfig
    template_name = 'accounting/voucher_config_detail.html'
    context_object_name = 'config'
    permission_required = ('accounting', 'vouchermodeconfig', 'view')

class ChartOfAccountListView(SmartListView):
    model = ChartOfAccount
    template_name = 'accounting/chart_of_accounts_list.html'
    context_object_name = 'accounts'
    permission_required = ('accounting', 'chartofaccount', 'view')
    
    def get_queryset(self):
        return super().get_queryset().order_by('account_code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:chart_of_accounts_create')
        context['create_button_text'] = 'New Chart of Account'
        return context
    
class CurrencyListView(SmartListView):
    model = Currency
    template_name = 'accounting/currency_list.html'
    context_object_name = 'currencies'
    permission_required = ('accounting', 'currency', 'view')

    def get_queryset(self):
        return Currency.objects.all().order_by('currency_code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:currency_create')
        context['create_button_text'] = 'New Currency'
        return context

class CurrencyExchangeRateListView(SmartListView):
    model = CurrencyExchangeRate
    template_name = 'accounting/currency_exchange_rate_list.html'
    context_object_name = 'exchange_rates'
    permission_required = ('accounting', 'currencyexchangerate', 'view')

    def get_queryset(self):
        qs = super().get_queryset().select_related('from_currency', 'to_currency').order_by('-rate_date')
        currency = self.request.GET.get('currency')
        if currency:
            qs = qs.filter(
                models.Q(from_currency__currency_code=currency) |
                models.Q(to_currency__currency_code=currency)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:exchange_rate_create')
        context['create_button_text'] = 'New Exchange Rate'
        context['currencies'] = Currency.objects.all().order_by('currency_code')
        context['selected_currency'] = self.request.GET.get('currency', '')
        return context


class TaxAuthorityListView(SmartListView):
    model = TaxAuthority
    template_name = 'accounting/tax_authority_list.html'
    context_object_name = 'tax_authorities'
    permission_required = ('accounting', 'taxauthority', 'view')

    def get_queryset(self):
        return super().get_queryset().order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:tax_authority_create')
        context['create_button_text'] = 'New Tax Authority'
        return context


class TaxTypeListView(SmartListView):
    model = TaxType
    template_name = 'accounting/tax_type_list.html'
    context_object_name = 'tax_types'
    permission_required = ('accounting', 'taxtype', 'view')

    def get_queryset(self):
        return super().get_queryset().order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:tax_type_create')
        context['create_button_text'] = 'New Tax Type'
        return context


class ProjectListView(SmartListView):
    model = Project
    template_name = 'accounting/project_list.html'
    context_object_name = 'projects'
    permission_required = ('accounting', 'project', 'view')

    def get_queryset(self):
        today = timezone.now().date()
        return super().get_queryset().filter(
            is_active=True
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=today),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:project_create')
        context['create_button_text'] = 'New Project'
        return context


class AccountingPeriodListView(SmartListView):
    model = AccountingPeriod
    template_name = 'accounting/accounting_period_list.html'
    context_object_name = 'accounting_periods'
    permission_required = ('accounting', 'accountingperiod', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:accounting_period_create')
        context['create_button_text'] = 'New Accounting Period'
        return context

class JournalDetailView(PermissionRequiredMixin, LoginRequiredMixin, DetailView):
    model = Journal
    template_name = 'accounting/journal_detail.html'
    context_object_name = 'journal'
    permission_required = ('accounting', 'journal', 'view')

class JournalPostView(LoginRequiredMixin, View):
    def post(self, request, pk):
        journal = get_object_or_404(Journal, pk=pk, organization=request.user.organization)
        if journal.status != 'draft':
            messages.error(request, 'Journal is not in draft status')
            return HttpResponseRedirect(reverse('accounting:journal_list'))
        try:
            from accounting.services.post_journal import post_journal, JournalPostingError, JournalValidationError

            post_journal(journal, user=request.user)
            messages.success(request, 'Journal posted and saved successfully.')
        except (JournalPostingError, JournalValidationError) as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('accounting:journal_list'))



# Chart of Accounts Views
class ChartOfAccountTreeListView(LoginRequiredMixin, ListView):
    model = ChartOfAccount
    template_name = 'accounting/chart_of_accounts_list.html'
    context_object_name = 'accounts'
    paginate_by = None  # Show all for tree

    def get_queryset(self):
        # Prefetch parent_account and account_type to avoid N+1
        organization = self.request.user.get_active_organization()
        if organization:
            return ChartOfAccount.objects.filter(
                organization_id=organization.id
            ).select_related('parent_account', 'account_type').order_by('account_code')
        else:
            return ChartOfAccount.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        accounts = list(self.get_queryset())
        # Build a tree structure
        tree = []
        id_map = {}
        for acc in accounts:
            acc.children = []
            acc.level = 0
            acc.indent_px = 0
            id_map[acc.account_id] = acc
        for acc in accounts:
            if acc.parent_account_id:
                parent = id_map.get(acc.parent_account_id)
                if parent:
                    acc.level = parent.level + 1
                    acc.indent_px = int(acc.level) * 20  # Ensure integer
                    parent.children.append(acc)
            else:
                acc.level = 0
                acc.indent_px = 0
                tree.append(acc)
        # Ensure children are lists, not querysets
        for acc in accounts:
            if not isinstance(acc.children, list):
                acc.children = list(acc.children)
        context['account_tree'] = tree
        context['create_url'] = reverse('accounting:chart_of_accounts_create')
        context['create_button_text'] = 'New Chart of Account'
        context['page_title'] = 'Chart of Accounts'
        context['breadcrumbs'] = [
            ('Chart of Accounts', None),
        ]
        # Remove columns/data/actions for table_tree.html
        # context['columns'] = ...
        # context['data'] = ...
        # context['actions'] = ...
        # Pass level=0 for the root include
        context['level'] = 0
        return context
    
class ChartOfAccountListPartial(ChartOfAccountTreeListView):
    """HTMX partial for chart of accounts list."""
    template_name = "accounting/chart_of_accounts_list_partial.html"

    @method_decorator(require_htmx)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


# Account Type Views
class AccountTypeListView(SmartListView):
    model = AccountType
    template_name = 'accounting/account_type_list.html'
    context_object_name = 'account_types'

    def get_queryset(self):
        return AccountType.objects.all().order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:account_type_create')
        context['create_button_text'] = 'New Account Type'
        return context

class VoucherUDFConfigListView(SmartListView):
    model = VoucherUDFConfig
    template_name = 'accounting/voucher_udf_config_list.html'
    context_object_name = 'udf_configs'
    permission_required = ('accounting', 'voucherudfconfig', 'view')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:voucher_udf_create')
        context['create_button_text'] = 'New Voucher UDF Config'
        return context

class GeneralLedgerListView(BaseListView):
    model = GeneralLedger
    template_name = 'accounting/general_ledger_list.html'
    context_object_name = 'gl_entries'
    permission_required = ('accounting', 'generalledger', 'view')

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'account', 'journal', 'period', 'department', 'cost_center'
        ).order_by('-transaction_date', '-created_at')

        # Apply filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        account_filter = self.request.GET.get('account')
        department_filter = self.request.GET.get('department')
        cost_center_filter = self.request.GET.get('cost_center')
        project_filter = self.request.GET.get('project')

        # If no filters are provided, return an empty queryset to avoid loading
        # the entire ledger which could be very large.
        if not any([start_date, end_date, account_filter, department_filter, cost_center_filter, project_filter]):
            return queryset.none()

        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)
        if account_filter:
            queryset = queryset.filter(account_id=account_filter)
        if department_filter:
            queryset = queryset.filter(department_id=department_filter)
        if cost_center_filter:
            queryset = queryset.filter(cost_center_id=cost_center_filter)
        if project_filter:
            queryset = queryset.filter(project=project_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).order_by('account_code')

        departments = Department.objects.filter(
            organization_id=organization.id, is_active=True
        ).order_by('name')

        cost_centers = CostCenter.objects.filter(
            organization_id=organization.id, is_active=True
        ).order_by('name')

        selected_account_text = ''
        account_filter_id = self.request.GET.get('account')
        if account_filter_id:
            try:
                selected_account = ChartOfAccount.objects.get(pk=account_filter_id, organization_id=organization.id)
                selected_account_text = f"{selected_account.account_code} - {selected_account.account_name}"
            except ChartOfAccount.DoesNotExist:
                pass

        context.update({
            'accounts': accounts,
            'departments': departments,
            'cost_centers': cost_centers,
            'selected_account_text': selected_account_text,
        })
        return context
class TaxCodeListView(BaseListView):
    model = TaxCode
    template_name = 'accounting/tax_code_list.html'
    context_object_name = 'tax_codes'
    permission_required = ('accounting', 'taxcode', 'view')

    def get_queryset(self):
        return super().get_queryset().order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:tax_code_create')
        context['create_button_text'] = 'New Tax Code'
        return context
# (Move all ListView classes for AccountType, Currency, TaxType, TaxAuthority, Project, AccountingPeriod, JournalType, etc. from views.py to this file)

 
