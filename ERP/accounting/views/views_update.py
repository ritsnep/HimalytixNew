from django.http import HttpResponse
from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from accounting.forms import TaxCodeForm
from accounting.views.views_mixins import UserOrganizationMixin, PermissionRequiredMixin
from accounting.mixins import AdvancedFormMixin
from accounting.models import *
# from accounting.forms import FiscalYearForm, CostCenterForm, VoucherModeConfigForm, VoucherModeDefaultForm, DepartmentForm, ChartOfAccountForm, VoucherUDFConfigForm, AccountTypeForm, CurrencyForm, TaxTypeForm, TaxAuthorityForm, ProjectForm, AccountingPeriodForm, JournalTypeForm, CurrencyExchangeRateForm, JournalForm
from accounting.forms import (
    FiscalYearForm,
    CostCenterForm,
    VoucherModeConfigForm,
    VoucherModeDefaultForm,
    DepartmentForm,
    ChartOfAccountForm,
    VoucherUDFConfigForm,
    AccountTypeForm,
    CurrencyForm,
    TaxTypeForm,
    TaxAuthorityForm,
    ProjectForm,
    AccountingPeriodForm,
    JournalTypeForm,
    CurrencyExchangeRateForm,
    JournalForm,
)
from accounting.forms.general_ledger_form import GeneralLedgerForm
from django.urls import reverse, reverse_lazy
from django.contrib import messages  # Add this import for messages
from django.db import transaction # Add this import for transaction
from django.shortcuts import get_object_or_404, redirect  # Add this import for get_object_or_404

class FiscalYearUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = FiscalYear
    form_class = FiscalYearForm
    template_name = "accounting/fiscal_year_form.html"
    success_url = reverse_lazy("accounting:fiscal_year_list")
    permission_required = ("accounting", "fiscalyear", "change")
    pk_url_kwarg = 'fiscal_year_id'

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form_title": "Update Fiscal Year",
                "back_url": reverse("accounting:fiscal_year_list"),
                "breadcrumbs": [
                    ("Fiscal Years", reverse("accounting:fiscal_year_list")),
                    ("Update Fiscal Year", None),
                ],
            }
        )
        return context


class JournalUpdateView(
    PermissionRequiredMixin, LoginRequiredMixin, UserOrganizationMixin, UpdateView
):
    model = Journal
    form_class = JournalForm
    template_name = "accounting/journal_form.html"
    permission_required = ("accounting", "journal", "change")

    def get_queryset(self):
        return Journal.objects.filter(
            organization_id=self.request.user.organization.id
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.user.get_active_organization()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context["form_title"] = "Edit Journal Entry"
        context["page_title"] = "Edit Journal Entry"
        context["breadcrumbs"] = [
            ("Journal Entries", reverse_lazy("accounting:journal_list")),
            (f"Edit: {obj.journal_number}", None),
        ]
        return context

    def form_valid(self, form):
        # Ensure the journal number is not changed if it already exists
        if (
            Journal.objects.filter(
                organization=self.request.user.organization,
                journal_number=form.cleaned_data["journal_number"],
            )
            .exclude(pk=self.object.pk)
            .exists()
        ):
            form.add_error(
                "journal_number",
                "This journal number already exists for this organization.",
            )
            return self.form_invalid(form)

        # Set updated_by field
        form.instance.updated_by = self.request.user

        return super().form_valid(form)

    success_url = reverse_lazy("accounting:journal_list")

class CostCenterUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = CostCenter
    form_class = CostCenterForm
    template_name = 'accounting/costcenter_form.html'
    success_url = reverse_lazy('accounting:costcenter_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs
    
    def get_queryset(self):
        return CostCenter.objects.filter(organization=self.request.user.organization)
    
    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Cost Center'
        context['back_url'] = reverse('accounting:costcenter_list')
        context['breadcrumbs'] = [
            ('Cost Centers', reverse('accounting:costcenter_list')),
            ('Update Cost Center', None)
        ]
        return context
    
class VoucherModeConfigUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = VoucherModeConfig
    form_class = VoucherModeConfigForm
    template_name = 'forms_designer/voucher_config_form.html'  # Use the new DRY template
    permission_required = ('accounting', 'vouchermodeconfig', 'change')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.instance.ui_schema = form.cleaned_data.get('ui_schema')
        messages.success(self.request, "Voucher configuration updated successfully.")
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if 'reset_to_default' in request.POST:
            self.object = self.get_object()
            self.object.ui_schema = default_ui_schema()
            self.object.save()
            messages.success(request, "Voucher configuration has been reset to default.")
            return redirect(self.get_success_url())
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('accounting:voucher_config_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update Voucher Configuration: {self.object.name}',
            'page_title': f'Update Voucher Configuration: {self.object.name}',
            'breadcrumbs': [
                ('Voucher Configurations', reverse('accounting:voucher_config_list')),
                (f'Update {self.object.name}', None)
            ]
        })
        return context
    
class VoucherModeDefaultUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = VoucherModeDefault
    form_class = VoucherModeDefaultForm
    template_name = 'accounting/voucher_default_form.html'
    permission_required = ('accounting', 'vouchermodedefault', 'change')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        kwargs['config_id'] = self.object.config_id
        return kwargs
    
    def get_success_url(self):
        return reverse_lazy('accounting:voucher_config_detail', kwargs={'pk': self.object.config_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = get_object_or_404(VoucherModeConfig, pk=self.object.config_id, organization_id=self.request.user.get_active_organization().id)
        context.update({
            'form_title': f'Update Default Line for {config.name}',
            'page_title': f'Update Default Line: {config.name}',
            'breadcrumbs': [
                ('Voucher Configurations', reverse('accounting:voucher_config_list')),
                (f'{config.name} Details', reverse('accounting:voucher_config_detail', kwargs={'pk': config.pk})),
                ('Update Default Line', None)
            ]
        })
        return context

class DepartmentUpdateView(LoginRequiredMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'accounting/department_form.html'
    success_url = reverse_lazy('accounting:department_list')
    
    def get_queryset(self):
        return Department.objects.all()
    
    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Department'
        context['back_url'] = reverse('accounting:department_list')
        context['breadcrumbs'] = [
            ('Departments', reverse('accounting:department_list')),
            ('Update Department', None)
        ]
        return context

class ChartOfAccountUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = ChartOfAccount
    form_class = ChartOfAccountForm
    template_name = 'accounting/chart_of_accounts_form_enhanced.html'
    success_url = reverse_lazy('accounting:chart_of_accounts_list')
    permission_required = ('accounting', 'chartofaccount', 'change')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def get_queryset(self):
        return ChartOfAccount.objects.filter(organization_id=self.request.user.organization.id)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                form.instance.updated_by = self.request.user
                
                # Save the form
                response = super().form_valid(form)
                
                # If it's an HTMX request, return a success message
                if self.request.headers.get('HX-Request'):
                    messages.success(self.request, "Chart of Account updated successfully.")
                    return HttpResponse(
                        '<div class="alert alert-success">Chart of Account updated successfully.</div>',
                        status=200
                    )
                
                messages.success(self.request, "Chart of Account updated successfully.")
                if self.request.POST.get('save_and_new') or self.request.POST.get('action') == 'save_new':
                    return redirect('accounting:chart_of_accounts_create')
                return response
                
        except Exception as e:
            logger.error(f"Error updating chart of account: {str(e)}")
            if self.request.headers.get('HX-Request'):
                return HttpResponse(
                    f'<div class="alert alert-danger">Error updating Chart of Account: {str(e)}</div>',
                    status=400
                )
            messages.error(self.request, f"Error updating Chart of Account: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="alert alert-danger">{" ".join([str(error) for error in form.non_field_errors()])}</div>',
                status=400
            )
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Edit Chart of Account',
            'page_title': 'Chart of Accounts',
            'list_url': reverse('accounting:chart_of_accounts_list'),
            'back_url': reverse('accounting:chart_of_accounts_list'),
            'breadcrumbs': [
                ('Chart of Accounts', reverse('accounting:chart_of_accounts_list')),
                ('Edit Chart of Account', None)
            ],
            # Point the enhanced form to the update endpoint
            'form_post_url': reverse('accounting:chart_of_accounts_update', kwargs={'pk': self.object.pk}),
            # Keep the enhanced layout but hide bulk/demo tabs for edit mode
            'enable_bulk_import': False,
            'enable_templates': False,
        })
        return context

    def handle_no_permission(self):
        logger.warning(f"User {self.request.user} denied permission to update ChartOfAccount {self.get_object().pk if self.get_object() else ''}")
        return super().handle_no_permission()

class VoucherUDFConfigUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = VoucherUDFConfig
    form_class = VoucherUDFConfigForm
    template_name = 'accounting/voucher_udf_form.html'
    permission_required = ('accounting', 'voucherudfconfig', 'change')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        kwargs['voucher_mode'] = self.object.voucher_mode
        return kwargs
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, "UDF configuration updated successfully.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('accounting:voucher_udf_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Update UDF Configuration: {self.object.display_name}',
            'page_title': f'Update UDF Configuration: {self.object.display_name}',
            'breadcrumbs': [
                ('Voucher UDF Configurations', reverse_lazy('accounting:voucher_udf_list')),
                (f'Update {self.object.display_name}', None)
            ]
        })
        return context

class AccountTypeUpdateView(AdvancedFormMixin, PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = AccountType
    form_class = AccountTypeForm
    template_name = 'accounting/account_type_form.html'
    success_url = reverse_lazy('accounting:account_type_list')
    permission_required = ('accounting', 'accounttype', 'change')

    # Advanced form configuration
    app_name = 'accounting'
    model_name = 'account_type'

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)

        if self.request.POST.get('save_and_new') or self.request.POST.get('action') == 'save_new':
            if self.request.headers.get('HX-Request'):
                hx_response = HttpResponse('', status=204)
                hx_response['HX-Redirect'] = reverse('accounting:account_type_create')
                return hx_response
            return redirect('accounting:account_type_create')

        if self.request.headers.get('HX-Request'):
            hx_response = HttpResponse('', status=204)
            hx_response['HX-Redirect'] = str(self.success_url)
            return hx_response

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Account Type'
        context['page_title'] = 'Account Type'
        context['list_url'] = reverse_lazy('accounting:account_type_list')
        context['back_url'] = reverse_lazy('accounting:account_type_list')
        context['form_post_url'] = reverse('accounting:account_type_update', kwargs={'pk': self.object.pk})
        context['can_save_and_new'] = True
        context['breadcrumbs'] = [
            ('Account Types', reverse_lazy('accounting:account_type_list')),
            ('Update Account Type', None)
        ]
        context['account_type_config'] = AccountType.get_ui_config()
        return context

class CurrencyUpdateView(AdvancedFormMixin, PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
    model = Currency
    form_class = CurrencyForm
    template_name = 'accounting/currency_form.html'
    success_url = reverse_lazy('accounting:currency_list')
    permission_required = ('accounting', 'currency', 'change')
    pk_url_kwarg = 'currency_code'
    
    # Advanced form configuration
    app_name = 'accounting'
    model_name = 'currency'

    def get_object(self, queryset=None):
        return self.model.objects.get(currency_code=self.kwargs['currency_code'])

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Currency'
        context['page_title'] = 'Currency'
        context['list_url'] = reverse_lazy('accounting:currency_list')
        context['back_url'] = reverse_lazy('accounting:currency_list')
        context['breadcrumbs'] = [
            ('Currencies', reverse_lazy('accounting:currency_list')),
            ('Update Currency', None)
        ]
        return context

class TaxTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = TaxType
    form_class = TaxTypeForm
    template_name = 'accounting/tax_type_form.html'
    success_url = reverse_lazy('accounting:tax_type_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Tax Type'
        context['back_url'] = reverse_lazy('accounting:tax_type_list')
        context['breadcrumbs'] = [
            ('Tax Types', reverse_lazy('accounting:tax_type_list')),
            ('Update Tax Type', None)
        ]
        return context

class TaxCodeUpdateView(LoginRequiredMixin, UpdateView):
    model = TaxCode
    form_class = TaxCodeForm
    template_name = 'accounting/tax_code_form.html'
    success_url = reverse_lazy('accounting:tax_code_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Tax Code'
        context['back_url'] = reverse_lazy('accounting:tax_code_list')
        context['breadcrumbs'] = [
            ('Tax Codes', reverse_lazy('accounting:tax_code_list')),
            ('Update Tax Code', None)
        ]
        return context

class TaxAuthorityUpdateView(LoginRequiredMixin, UpdateView):
    model = TaxAuthority
    form_class = TaxAuthorityForm
    template_name = 'accounting/tax_authority_form.html'
    success_url = reverse_lazy('accounting:tax_authority_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Tax Authority'
        context['back_url'] = reverse_lazy('accounting:tax_authority_list')
        context['breadcrumbs'] = [
            ('Tax Authorities', reverse_lazy('accounting:tax_authority_list')),
            ('Update Tax Authority', None)
        ]
        return context

class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'accounting/project_form.html'
    success_url = reverse_lazy('accounting:project_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Project'
        context['back_url'] = reverse_lazy('accounting:project_list')
        context['breadcrumbs'] = [
            ('Projects', reverse_lazy('accounting:project_list')),
            ('Update Project', None)
        ]
        return context

class AccountingPeriodUpdateView(LoginRequiredMixin, UpdateView):
    model = AccountingPeriod
    form_class = AccountingPeriodForm
    template_name = 'accounting/accounting_period_form.html'
    success_url = reverse_lazy('accounting:accounting_period_list')
    pk_url_kwarg = 'period_id'

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_queryset(self):
        return super().get_queryset().filter(
            organization=self.request.user.organization
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Accounting Period'
        context['back_url'] = reverse_lazy('accounting:accounting_period_list')
        context['breadcrumbs'] = [
            ('Accounting Periods', reverse_lazy('accounting:accounting_period_list')),
            ('Update Accounting Period', None)
        ]
        return context

class JournalTypeUpdateView(LoginRequiredMixin, UpdateView):
    model = JournalType
    form_class = JournalTypeForm
    template_name = 'accounting/journal_type_form.html'
    success_url = reverse_lazy('accounting:journal_type_list')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Journal Type'
        context['back_url'] = reverse_lazy('accounting:journal_type_list')
        context['breadcrumbs'] = [
            ('Journal Types', reverse_lazy('accounting:journal_type_list')),
            ('Update Journal Type', None)
        ]
        return context

class CurrencyExchangeRateUpdateView(LoginRequiredMixin, UpdateView):
    model = CurrencyExchangeRate
    form_class = CurrencyExchangeRateForm
    template_name = 'accounting/currency_exchange_rate_form.html'
    success_url = reverse_lazy('accounting:exchange_rate_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.organization
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Update Exchange Rate'
        context['back_url'] = reverse_lazy('accounting:exchange_rate_list')
        context['breadcrumbs'] = [
            ('Exchange Rates', reverse_lazy('accounting:exchange_rate_list')),
            ('Update Exchange Rate', None)
        ]
        return context

class GeneralLedgerUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    model = GeneralLedger
    form_class = GeneralLedgerForm
    template_name = 'accounting/general_ledger_form.html'
    success_url = reverse_lazy('accounting:generalledger-list')
    permission_required = ('accounting', 'generalledger', 'change')

    def get_queryset(self):
        return GeneralLedger.objects.filter(organization_id=self.request.user.organization.id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Edit General Ledger'
        context['page_title'] = 'Edit General Ledger'
        context['breadcrumbs'] = [
            ('General Ledger', reverse_lazy('accounting:generalledger-list')),
            (f'Edit: {obj.id}', None)
        ]
        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        return super().form_valid(form)
