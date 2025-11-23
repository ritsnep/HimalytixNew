from django.forms import ValidationError
from accounting.models import *
from accounting.forms import (
    CostCenterForm, TaxTypeForm, TaxAuthorityForm, AccountTypeForm,
    CurrencyForm, CurrencyExchangeRateForm, VoucherModeDefaultForm,
    ProjectForm, AccountingPeriodForm, DepartmentForm, JournalTypeForm,
    FiscalYearForm, ChartOfAccountForm, VoucherModeConfigForm,
    JournalForm, JournalLineForm, JournalLineFormSet, VoucherUDFConfigForm,
    GeneralLedgerForm, TaxCodeForm
)

from accounting.forms.general_ledger_form import GeneralLedgerForm
from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounting.views.views_mixins import UserOrganizationMixin, PermissionRequiredMixin
from django.urls import reverse, reverse_lazy
from django.contrib import messages  # Add this import for messages
from django.db import transaction    # Add this import for transaction
from django.http import HttpResponseServerError, HttpResponse  # Add this import for error handling and HttpResponse
from django.shortcuts import get_object_or_404, redirect  # Add this import for get_object_or_404
import logging

logger = logging.getLogger(__name__)

class FiscalYearCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = FiscalYear
    form_class = FiscalYearForm
    template_name = 'accounting/fiscal_year_form.html'
    success_url = reverse_lazy('accounting:fiscal_year_list')
    permission_required = ('accounting', 'fiscalyear', 'add')

    def clean(self):
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be before end date.")

    def get_initial(self):
        initial = super().get_initial()
        from accounting.models import AutoIncrementCodeGenerator
        organization = self.request.user.get_active_organization()
        code_generator = AutoIncrementCodeGenerator(
            FiscalYear,
            'code',
            organization=organization,
            prefix='FY',
            suffix='',
        )
        initial['code'] = code_generator.generate_code()
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Fiscal year created successfully.")
        form.instance.organization = self.request.user.get_active_organization()
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Fiscal Year'
        context['back_url'] = reverse('accounting:fiscal_year_list')
        return context

class CostCenterCreateView(LoginRequiredMixin, UserOrganizationMixin, CreateView):
    model = CostCenter
    form_class = CostCenterForm
    template_name = 'accounting/costcenter_form.html'
    success_url = reverse_lazy('accounting:costcenter_list')
    
    def form_valid(self, form):
        form.instance.organization = self.request.user.organization 
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Cost Center'
        context['back_url'] = reverse('accounting:costcenter_list')
        context['breadcrumbs'] = [
            ('Cost Centers', reverse('accounting:costcenter_list')),
            ('Create Cost Center', None)
        ]
        return context

class TaxTypeCreateView(LoginRequiredMixin, CreateView):
    model = TaxType
    form_class = TaxTypeForm
    template_name = 'accounting/tax_type_form.html'
    success_url = reverse_lazy('accounting:tax_type_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Tax Type'
        context['back_url'] = reverse('accounting:tax_type_list')
        context['breadcrumbs'] = [
            ('Tax Types', reverse('accounting:tax_type_list')),
            ('Create Tax Type', None)
        ]
        return context
 
class TaxAuthorityCreateView(LoginRequiredMixin, CreateView):
    model = TaxAuthority
    form_class = TaxAuthorityForm
    template_name = 'accounting/tax_authority_form.html'
    success_url = reverse_lazy('accounting:tax_authority_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Tax Authority'
        context['back_url'] = reverse('accounting:tax_authority_list')
        context['breadcrumbs'] = [
            ('Tax Authorities', reverse('accounting:tax_authority_list')),
            ('Create Tax Authority', None)
        ]
        return context


class AccountTypeCreateView(LoginRequiredMixin, CreateView):
    model = AccountType
    form_class = AccountTypeForm
    template_name = 'accounting/account_type_form.html'
    success_url = reverse_lazy('accounting:account_type_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"AccountType form errors: {form.errors.as_json()}")
        # Add Django messages for each error
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Account Type'
        context['back_url'] = reverse('accounting:account_type_list')
        context['breadcrumbs'] = [
            ('Account Types', reverse('accounting:account_type_list')),
            ('Create Account Type', None)
        ]
        return context


class ChartOfAccountCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = ChartOfAccount
    form_class = ChartOfAccountForm
    template_name = 'accounting/chart_of_accounts_form.html'
    success_url = reverse_lazy('accounting:chart_of_accounts_list')
    permission_required = ('accounting', 'chartofaccount', 'add')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Allow pre-selecting parent/account_type via query params for better UX
        parent = self.request.GET.get('parent')
        if parent:
            initial['parent_account'] = parent
        account_type = self.request.GET.get('account_type')
        if account_type:
            initial['account_type'] = account_type
        return initial

    def form_valid(self, form):
        try:
            with transaction.atomic():
                form.instance.organization = self.get_organization()
                form.instance.created_by = self.request.user
                
                # Save the form
                response = super().form_valid(form)
                
                # If it's an HTMX request, return a success message
                if self.request.headers.get('HX-Request'):
                    messages.success(self.request, "Chart of Account created successfully.")
                    return HttpResponse(
                        f'<div class="alert alert-success">Chart of Account created successfully. Redirecting...</div>'
                        f'<script>setTimeout(function() {{ window.location.href = "{self.success_url}"; }}, 1000);</script>',
                        status=200
                    )
                
                messages.success(self.request, "Chart of Account created successfully.")
                # Support Save & New button
                if self.request.POST.get('action') == 'save_new':
                    return redirect('accounting:chart_of_accounts_create')
                return response
                
        except Exception as e:
            logger.error(f"Error creating chart of account: {str(e)}")
            if self.request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="alert alert-danger">Error creating Chart of Account: {str(e)}</div>',
                    status=400
                )
            messages.error(self.request, f"Error creating Chart of Account: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.error(f"Form validation errors: {form.errors}")
        if self.request.headers.get('HX-Request'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(form=form), request=self.request)
            return HttpResponse(html, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create Chart of Account',
            'page_title': 'Create Chart of Account',
            'breadcrumbs': [
                ('Chart of Accounts', reverse('accounting:chart_of_accounts_list')),
                ('Create Chart of Account', None)
            ],
            'form_post_url': reverse('accounting:chart_of_accounts_create')
        })
        return context

class CurrencyCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = Currency
    form_class = CurrencyForm
    template_name = 'accounting/currency_form.html'
    success_url = reverse_lazy('accounting:currency_list')
    permission_required = ('accounting', 'currency', 'add')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Currency'
        context['back_url'] = reverse('accounting:currency_list')
        context['breadcrumbs'] = [
            ('Currencies', reverse('accounting:currency_list')),
            ('Create Currency', None)
        ]
        return context

class CurrencyExchangeRateCreateView(LoginRequiredMixin, CreateView):
    model = CurrencyExchangeRate
    form_class = CurrencyExchangeRateForm
    template_name = 'accounting/currency_exchange_rate_form.html'
    success_url = reverse_lazy('accounting:exchange_rate_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        messages.success(self.request, "Currency exchange rate created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Exchange Rate'
        context['back_url'] = reverse('accounting:exchange_rate_list')
        context['breadcrumbs'] = [
            ('Exchange Rates', reverse('accounting:exchange_rate_list')),
            ('Create Exchange Rate', None)
        ]
        return context

class VoucherModeConfigCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = VoucherModeConfig
    form_class = VoucherModeConfigForm
    template_name = 'accounting/voucher_config_form.html'
    permission_required = ('accounting', 'vouchermodeconfig', 'add')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs
    
    def form_valid(self, form):
        form.instance.organization = self.request.user.get_active_organization()
        form.instance.created_by = self.request.user
        form.instance.ui_schema = form.cleaned_data.get('ui_schema')
        messages.success(self.request, "Voucher configuration created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('accounting:voucher_config_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create Voucher Configuration',
            'page_title': 'Create Voucher Configuration',
            'breadcrumbs': [
                ('Voucher Configurations', reverse('accounting:voucher_config_list')),
                ('Create Voucher Configuration', None)
            ]
        })
        return context


class VoucherModeDefaultCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = VoucherModeDefault
    form_class = VoucherModeDefaultForm
    template_name = 'accounting/voucher_default_form.html'
    permission_required = ('accounting', 'vouchermodedefault', 'add')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        # kwargs['config_id'] = self.kwargs['config_id']
        return kwargs
    
    def form_valid(self, form):
        config = get_object_or_404(VoucherModeConfig, pk=self.kwargs['config_id'], organization=self.request.user.get_active_organization())
        form.instance.config = config
        messages.success(self.request, "Voucher default line created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('accounting:voucher_config_detail', kwargs={'pk': self.kwargs['config_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = get_object_or_404(VoucherModeConfig, pk=self.kwargs['config_id'], organization=self.request.user.get_active_organization())
        context.update({
            'config_id': self.kwargs['config_id'],
            'form_title': f'Add Default Line to {config.name}',
            'page_title': f'Add Default Line: {config.name}',
            'breadcrumbs': [
                ('Voucher Configurations', reverse('accounting:voucher_config_list')),
                (f'{config.name} Details', reverse('accounting:voucher_config_detail', kwargs={'pk': config.pk})),
                ('Add Default Line', None)
            ]
        })
        return context


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'accounting/project_form.html'
    success_url = reverse_lazy('accounting:project_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Project'
        context['back_url'] = reverse('accounting:project_list')
        context['breadcrumbs'] = [
            ('Projects', reverse('accounting:project_list')),
            ('Create Project', None)
        ]
        return context

class AccountingPeriodCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = AccountingPeriod
    form_class = AccountingPeriodForm
    template_name = 'accounting/accounting_period_form.html'
    success_url = reverse_lazy('accounting:accounting_period_list')
    permission_required = ('accounting', 'accountingperiod', 'add')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs


    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Accounting Period'
        context['back_url'] = reverse('accounting:accounting_period_list')
        return context

class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'accounting/department_form.html'
    success_url = reverse_lazy('accounting:department_list')
    
    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Department'
        context['back_url'] = reverse('accounting:department_list')
        context['breadcrumbs'] = [
            ('Departments', reverse('accounting:department_list')),
            ('Create Department', None)
        ]
        return context


class JournalTypeCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = JournalType
    form_class = JournalTypeForm
    template_name = 'accounting/journal_type_form.html'
    success_url = reverse_lazy('accounting:journal_type_list')
    permission_required = ('accounting', 'journaltype', 'add')

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Journal Type'
        context['back_url'] = reverse('accounting:journal_type_list')
        return context

class JournalCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    """Create new journal entry with dynamic form."""
    model = Journal
    template_name = 'accounting/journal_form.html'
    permission_required = ('accounting', 'journal', 'add')

    def get_form_class(self):
        # Use dynamic form based on journal type
        journal_type_id = self.request.GET.get('journal_type')
        if journal_type_id:
            try:
                journal_type = JournalType.objects.get(
                    journal_type_id=journal_type_id,
                    organization_id=self.request.user.get_active_organization().id
                )
                return self.build_dynamic_form(journal_type)
            except JournalType.DoesNotExist:
                pass
        return JournalForm

    def build_dynamic_form(self, journal_type):
        from accounting.forms import JournalForm
        class DynamicJournalForm(JournalForm):
            class Meta(JournalForm.Meta):
                pass
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.journal_type = journal_type
                udf_configs = VoucherUDFConfig.objects.filter(
                    voucher_mode__journal_type=journal_type,
                    scope='header',
                    is_active=True
                ).order_by('display_order')
                for udf in udf_configs:
                    field = self.create_udf_field(udf)
                    self.fields[udf.field_name] = field
        return DynamicJournalForm

    def create_udf_field(self, udf_config):
        from django import forms
        field_kwargs = {
            'label': udf_config.display_name,
            'required': udf_config.is_required,
            'help_text': udf_config.help_text,
        }
        if udf_config.field_type == 'text':
            field = forms.CharField(max_length=udf_config.max_length or 255, **field_kwargs)
        elif udf_config.field_type == 'number':
            field = forms.IntegerField(**field_kwargs)
        elif udf_config.field_type == 'decimal':
            field = forms.DecimalField(max_digits=19, decimal_places=4, **field_kwargs)
        elif udf_config.field_type == 'date':
            field = forms.DateField(**field_kwargs)
        elif udf_config.field_type == 'datetime':
            field = forms.DateTimeField(**field_kwargs)
        elif udf_config.field_type == 'select':
            choices = [(choice, choice) for choice in udf_config.choices or []]
            field = forms.ChoiceField(choices=choices, **field_kwargs)
        elif udf_config.field_type == 'checkbox':
            field = forms.BooleanField(required=False, **field_kwargs)
        elif udf_config.field_type == 'textarea':
            field = forms.CharField(widget=forms.Textarea, **field_kwargs)
        else:
            field = forms.CharField(**field_kwargs)
        if udf_config.default_value:
            field.initial = udf_config.default_value
        return field

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.user.get_active_organization()
        form.instance.created_by = self.request.user
        journal_type = form.cleaned_data.get('journal_type')
        if journal_type:
            form.instance.journal_number = journal_type.get_next_journal_number()
        response = super().form_valid(form)
        lines_data = self.request.POST.getlist('lines')
        if lines_data:
            self.save_journal_lines(form.instance, lines_data)
        messages.success(self.request, "Journal entry created successfully.")
        return response

    def save_journal_lines(self, journal, lines_data):
        for i, line_data in enumerate(lines_data):
            if not line_data.strip():
                continue
            try:
                import json
                data = json.loads(line_data)
                JournalLine.objects.create(
                    journal=journal,
                    line_number=i + 1,
                    account_id=data.get('account_id'),
                    description=data.get('description', ''),
                    debit_amount=data.get('debit_amount', 0),
                    credit_amount=data.get('credit_amount', 0),
                    department_id=data.get('department_id'),
                    project_id=data.get('project_id'),
                    cost_center_id=data.get('cost_center_id'),
                    created_by=self.request.user
                )
            except (json.JSONDecodeError, KeyError):
                continue

    def get_success_url(self):
        return reverse('accounting:journal_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.get_active_organization()
        journal_types = JournalType.objects.filter(
            organization_id=organization.id,
            is_active=True
        )
        accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).order_by('account_code')
        context.update({
            'journal_types': journal_types,
            'accounts': accounts,
            'page_title': 'New Journal Entry',
            'breadcrumbs': [
                ('General Journal', reverse('accounting:journal_list')),
                ('New Entry', None)
            ],
        })
        return context

class VoucherUDFConfigCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = VoucherUDFConfig
    form_class = VoucherUDFConfigForm
    template_name = 'accounting/voucher_udf_form.html'
    permission_required = ('accounting', 'voucherudfconfig', 'add')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        voucher_mode_id = self.request.GET.get('voucher_mode')
        if voucher_mode_id:
            kwargs['voucher_mode'] = get_object_or_404(
                VoucherModeConfig, 
                pk=voucher_mode_id,
                organization_id=self.request.user.get_active_organization().id
            )
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "UDF configuration created successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('accounting:voucher_udf_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create New UDF Configuration',
            'page_title': 'Create New UDF Configuration',
            'breadcrumbs': [
                ('Voucher UDF Configurations', reverse_lazy('accounting:voucher_udf_list')),
                ('Create New', None)
            ]
        })
        return context

class TaxCodeCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = TaxCode
    form_class = TaxCodeForm
    template_name = 'accounting/tax_code_form.html'
    success_url = reverse_lazy('accounting:tax_code_list')
    permission_required = ('accounting', 'taxcode', 'add')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Tax Code'
        context['back_url'] = reverse('accounting:tax_code_list')
        context['breadcrumbs'] = [
            ('Tax Codes', reverse('accounting:tax_code_list')),
            ('Create Tax Code', None)
        ]
        return context

class GeneralLedgerCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = GeneralLedger
    form_class = GeneralLedgerForm
    template_name = 'accounting/general_ledger_form.html'
    success_url = reverse_lazy('accounting:general_ledger_list')
    permission_required = ('accounting', 'generalledger', 'add')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.get_organization()
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.get_organization()
        form.instance.created_by = self.request.user
        messages.success(self.request, "General Ledger entry created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create General Ledger Entry',
            'page_title': 'Create General Ledger Entry',
            'breadcrumbs': [
                ('General Ledger', reverse('accounting:general_ledger_list')),
                ('Create Entry', None)
            ]
        })
        return context
