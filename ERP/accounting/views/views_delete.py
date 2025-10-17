from accounting.models import *
from accounting.forms import VoucherUDFConfigForm
from django.views.generic import DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from accounting.views.views_mixins import UserOrganizationMixin, PermissionRequiredMixin
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator  # Add this import for method_decorator
from usermanagement.utils import require_permission   # Add this import for require_permission
from accounting.models import VoucherUDFConfig
from accounting.models import JournalType
from accounting.models import VoucherModeConfig
from accounting.models import Currency
from accounting.models import CurrencyExchangeRate
from accounting.models import TaxAuthority
from accounting.models import TaxType

class AccountTypeDeleteView(LoginRequiredMixin, DeleteView):
    model = AccountType
    template_name = 'accounting/account_type_confirm_delete.html'
    success_url = reverse_lazy('accounting:account_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Account Type'
        context['page_title'] = 'Delete Account Type'
        context['breadcrumbs'] = [
            ('Account Types', reverse_lazy('accounting:account_type_list')),
            (f'Delete: {obj.code} - {obj.name}', None)
        ]
        return context

# Add other DeleteView classes here as needed

class VoucherModeDefaultDeleteView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = ('accounting', 'vouchermodedefault', 'delete')
    
    def post(self, request, pk):
        default = get_object_or_404(VoucherModeDefault, pk=pk, config__organization_id=request.user.get_active_organization().id)
        config_id = default.config_id
        default.delete()
        messages.success(request, "Voucher default line deleted successfully.")
        return redirect(reverse_lazy('accounting:voucher_config_detail', kwargs={'pk': config_id}))

class ChartOfAccountDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = ChartOfAccount
    template_name = 'accounting/chart_of_accounts_confirm_delete.html'
    success_url = reverse_lazy('accounting:chart_of_accounts_list')
    permission_required = ('accounting', 'chartofaccount', 'delete')

    def get_queryset(self):
        return ChartOfAccount.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Chart of Account'
        context['page_title'] = 'Delete Chart of Account'
        context['breadcrumbs'] = [
            ('Chart of Accounts', reverse_lazy('accounting:chart_of_accounts_list')),
            (f'Delete: {obj.account_code} - {obj.account_name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if ChartOfAccount.objects.filter(parent_account_id=self.object.pk).exists():
            messages.error(request, "Cannot delete an account that has sub-accounts. Please remove or reassign its children first.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

    def handle_no_permission(self):
        logger.warning(f"User {self.request.user} denied permission to delete ChartOfAccount {self.get_object().pk if self.get_object() else ''}")
        return super().handle_no_permission()

class VoucherUDFConfigDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = VoucherUDFConfig
    template_name = 'accounting/voucher_udf_config_confirm_delete.html'
    context_object_name = 'udf_config'
    permission_required = ('accounting', 'voucherudfconfig', 'delete')
    success_url = reverse_lazy('accounting:voucher_udf_list')

class JournalTypeDeleteView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = ('accounting', 'journaltype', 'delete')
    
    def post(self, request, journal_type_id):
        journal_type = get_object_or_404(
            JournalType, 
            journal_type_id=journal_type_id,
            organization_id=request.user.get_active_organization().id
        )
        
        if getattr(journal_type, 'is_system_type', False):
            messages.error(request, "System journal types cannot be deleted.")
            return redirect('accounting:journal_type_list')
        
        # Check if there are any journals using this type
        if hasattr(journal_type, 'journals') and journal_type.journals.exists():
            messages.error(request, f"Cannot delete journal type '{journal_type.name}' because it has associated journals.")
            return redirect('accounting:journal_type_list')
        
        journal_type_name = journal_type.name
        journal_type.delete()
        messages.success(request, f"Journal type '{journal_type_name}' deleted successfully.")
        return redirect('accounting:journal_type_list')

class FiscalYearDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = FiscalYear
    template_name = 'accounting/fiscal_year_confirm_delete.html'
    success_url = reverse_lazy('accounting:fiscal_year_list')
    permission_required = ('accounting', 'fiscalyear', 'delete')

    def get_queryset(self):
        return FiscalYear.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Fiscal Year'
        context['page_title'] = 'Delete Fiscal Year'
        context['breadcrumbs'] = [
            ('Fiscal Years', reverse_lazy('accounting:fiscal_year_list')),
            (f'Delete: {obj.code} - {obj.name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.periods.exists():
            messages.error(request, "Cannot delete a fiscal year that has accounting periods. Please remove them first.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

class AccountingPeriodDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = AccountingPeriod
    template_name = 'accounting/accounting_period_confirm_delete.html'
    success_url = reverse_lazy('accounting:accounting_period_list')
    permission_required = ('accounting', 'accountingperiod', 'delete')

    def get_queryset(self):
        return AccountingPeriod.objects.filter(fiscal_year__organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Accounting Period'
        context['page_title'] = 'Delete Accounting Period'
        context['breadcrumbs'] = [
            ('Accounting Periods', reverse_lazy('accounting:accounting_period_list')),
            (f'Delete: {obj.name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.journal_set.exists():
            
            messages.error(
                request,
                "Cannot delete an accounting period that has journals associated with it.",
            )
            return redirect(self.success_url)
        if self.object.is_current or (
            self.object.status == 'open'
            and not AccountingPeriod.objects.filter(
                fiscal_year=self.object.fiscal_year, status='open'
            )
            .exclude(pk=self.object.pk)
            .exists()
        ):
            messages.error(
                request,
                "Cannot delete the current or only open accounting period.",
            )
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

class DepartmentDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Department
    template_name = 'accounting/department_confirm_delete.html'
    success_url = reverse_lazy('accounting:department_list')
    permission_required = ('accounting', 'department', 'delete')

    def get_queryset(self):
        return Department.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Department'
        context['page_title'] = 'Delete Department'
        context['breadcrumbs'] = [
            ('Departments', reverse_lazy('accounting:department_list')),
            (f'Delete: {obj.name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.journal_lines.exists():
            messages.error(request, "Cannot delete a department that has journal lines associated with it.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

class ProjectDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Project
    template_name = 'accounting/project_confirm_delete.html'
    success_url = reverse_lazy('accounting:project_list')
    permission_required = ('accounting', 'project', 'delete')

    def get_queryset(self):
        return Project.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Project'
        context['page_title'] = 'Delete Project'
        context['breadcrumbs'] = [
            ('Projects', reverse_lazy('accounting:project_list')),
            (f'Delete: {obj.name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.journal_lines.exists():
            messages.error(request, "Cannot delete a project that has journal lines associated with it.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

class CostCenterDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = CostCenter
    template_name = 'accounting/cost_center_confirm_delete.html'
    success_url = reverse_lazy('accounting:costcenter_list')
    permission_required = ('accounting', 'costcenter', 'delete')

    def get_queryset(self):
        return CostCenter.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Cost Center'
        context['page_title'] = 'Delete Cost Center'
        context['breadcrumbs'] = [
            ('Cost Centers', reverse_lazy('accounting:costcenter_list')),
            (f'Delete: {obj.name}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.journal_lines.exists():
            messages.error(request, "Cannot delete a cost center that has journal lines associated with it.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

class JournalDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Journal
    template_name = 'accounting/journal_confirm_delete.html'
    success_url = reverse_lazy('accounting:journal_list')
    permission_required = ('accounting', 'journal', 'delete')

    def get_queryset(self):
        return Journal.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete Journal Entry'
        context['page_title'] = 'Delete Journal Entry'
        context['breadcrumbs'] = [
            ('Journal Entries', reverse_lazy('accounting:journal_list')),
            (f'Delete: {obj.journal_number}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status not in ['draft', 'rejected']:
            messages.error(request, "Cannot delete a journal entry that has been posted or approved.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)
class GeneralLedgerDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = GeneralLedger
    template_name = 'accounting/general_ledger_confirm_delete.html'
    success_url = reverse_lazy('accounting:general_ledger_list')
    permission_required = ('accounting', 'generalledger', 'delete')

    def get_queryset(self):
        return GeneralLedger.objects.filter(organization_id=self.request.user.organization.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.get_object()
        context['form_title'] = 'Delete General Ledger Entry'
        context['page_title'] = 'Delete General Ledger Entry'
        context['breadcrumbs'] = [
            ('General Ledger', reverse_lazy('accounting:general_ledger_list')),
            (f'Delete: {obj.gl_entry_id}', None)
        ]
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Add any specific checks here, e.g., if the entry is already posted or part of a closed period.
        # For now, we'll assume direct deletion is allowed if the user has permission.
        if self.object.journal.status not in ['draft', 'rejected']:
            messages.error(request, "Cannot delete a General Ledger entry associated with a posted or approved journal.")
            return redirect(self.success_url)
        return super().delete(request, *args, **kwargs)

class VoucherModeConfigDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = VoucherModeConfig
    template_name = 'accounting/voucher_mode_config_confirm_delete.html'
    success_url = reverse_lazy('accounting:voucher_config_list')
    permission_required = ('accounting', 'vouchermodeconfig', 'delete')

    def get_queryset(self):
        return VoucherModeConfig.objects.filter(organization_id=self.request.user.get_active_organization().id)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f"Voucher Mode Config '{self.object.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

class CurrencyDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = Currency
    template_name = 'accounting/currency_confirm_delete.html'
    success_url = reverse_lazy('accounting:currency_list')
    permission_required = ('accounting', 'currency', 'delete')
    pk_url_kwarg = 'currency_code'
    slug_field = 'currency_code'
    slug_url_kwarg = 'currency_code'

    def get_object(self, queryset=None):
        return self.model.objects.get(currency_code=self.kwargs['currency_code'])

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f"Currency '{self.object.currency_code}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

class CurrencyExchangeRateDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = CurrencyExchangeRate
    template_name = 'accounting/currency_exchange_rate_confirm_delete.html'
    success_url = reverse_lazy('accounting:exchange_rate_list')
    permission_required = ('accounting', 'currencyexchangerate', 'delete')

    def get_queryset(self):
        return CurrencyExchangeRate.objects.filter(organization=self.request.user.organization)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if JournalLine.objects.filter(tax_code=self.object).exists():
            messages.error(request, f"Cannot delete tax code '{self.object.code}' because it is used in journal lines.")
            return redirect('accounting:tax_code_list')
        messages.success(request, f"Exchange rate deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
class TaxCodeDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = TaxCode
    template_name = 'accounting/tax_code_confirm_delete.html'
    success_url = reverse_lazy('accounting:tax_code_list')
    permission_required = ('accounting', 'taxcode', 'delete')

    def get_queryset(self):
        return TaxCode.objects.filter(organization=self.request.user.organization)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f"Tax Code '{self.object.code}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

class TaxAuthorityDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = TaxAuthority
    template_name = 'accounting/tax_authority_confirm_delete.html'
    success_url = reverse_lazy('accounting:tax_authority_list')
    permission_required = ('accounting', 'taxauthority', 'delete')

    def get_queryset(self):
        return TaxAuthority.objects.filter(organization=self.request.user.organization)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(request, f"Tax Authority '{self.object.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)

class TaxTypeDeleteView(PermissionRequiredMixin, LoginRequiredMixin, DeleteView):
    model = TaxType
    template_name = 'accounting/tax_type_confirm_delete.html'
    success_url = reverse_lazy('accounting:tax_type_list')
    permission_required = ('accounting', 'taxtype', 'delete')

    def get_queryset(self):
        return TaxType.objects.filter(organization=self.request.user.organization)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.taxcode_set.exists():
            messages.error(request, f"Cannot delete tax type '{self.object.name}' because it has associated tax codes.")
            return redirect('accounting:tax_type_list')
        messages.success(request, f"Tax Type '{self.object.name}' deleted successfully.")
        return super().delete(request, *args, **kwargs)
