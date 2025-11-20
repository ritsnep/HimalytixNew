from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView,  UpdateView, DetailView, TemplateView, CreateView
from django.urls import reverse, reverse_lazy
from django.http import HttpResponseForbidden, HttpResponseServerError, JsonResponse, HttpResponse
import json
import csv
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from accounting.models import AccountType, Currency, CurrencyExchangeRate, FiscalYear, TaxAuthority, TaxType
from accounting.forms import AccountTypeForm, ChartOfAccountForm, CostCenterForm, CurrencyExchangeRateForm, CurrencyForm, DepartmentForm, FiscalYearForm, ProjectForm, TaxAuthorityForm, TaxTypeForm
from django.contrib import messages
from django.db.models import F
from django.http import JsonResponse
from accounting.models import ChartOfAccount  # adjust as needed

from accounting.serializers import VoucherModeConfigSerializer

from accounting.models import (
    FiscalYear, GeneralLedger, Journal, JournalLine, JournalType, ChartOfAccount, 
    AccountingPeriod, TaxCode, Department, Project, CostCenter,
    VoucherModeConfig, VoucherModeDefault, VoucherUDFConfig
)
from accounting.forms import (
    JournalForm, JournalLineForm, JournalLineFormSet,
    VoucherModeConfigForm, VoucherModeDefaultForm, VoucherUDFConfigForm, AccountingPeriodForm, JournalTypeForm
)


from django.urls import reverse_lazy
from accounting.services.create_voucher import create_voucher
from utils.htmx import require_htmx
from usermanagement.utils import require_permission
from usermanagement.utils import PermissionUtils
from django.forms import inlineformset_factory

from voucher_schema.loader import load_schema
from .views_mixins import UserOrganizationMixin, PermissionRequiredMixin, VoucherConfigMixin
from .views_list import GeneralLedgerListView
from .views_create import *
from accounting.services.close_period import close_period
from .views_update import *
from .views_delete import *
from .views_htmx import VoucherConfigListHXView
from accounting.forms import ChartOfAccountForm
from django.views.decorators.csrf import csrf_exempt
from utils.form_restore import get_pending_form_initial, clear_pending_form
from django.db.models import Prefetch
import logging
from decimal import Decimal
from django.db.models import Sum
from accounting.forms_factory import build_form, build_formset
from django.forms import formset_factory
from accounting.schema_loader import load_voucher_schema
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from accounting.services.post_journal import JournalPostingError, post_journal, JournalError, JournalValidationError
from django.http import JsonResponse, HttpResponseForbidden
from accounting.models import JournalLine
from accounting.validation import JournalValidationService
from accounting.views.report_views import build_report_cards

logger = logging.getLogger(__name__)

def _inject_udfs_into_schema(schema, udf_configs):
    """Injects UDF configurations into the header and lines schema."""
    header_schema = schema.get("header", {})
    lines_schema = schema.get("lines", {})

    for udf in udf_configs:
        udf_schema = {
            "name": f"udf_{udf.field_name}",
            "label": udf.field_label,
            "type": udf.field_type,
            "required": udf.is_required,
            "choices": udf.choices or [],
        }
        if udf.scope == 'header':
            header_schema.setdefault('fields', []).append(udf_schema)
        elif udf.scope == 'line':
            lines_schema.setdefault('fields', []).append(udf_schema)
    return schema

class HTMXAccountAutocompleteView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('query', '')
        accounts = ChartOfAccount.objects.filter(
            organization_id=request.user.get_active_organization().id,
            account_code__icontains=query
        )[:10]
        results = [{'id': a.account_id, 'text': f"{a.account_code} - {a.account_name}"} for a in accounts]
        return JsonResponse({'results': results})

# Voucher Mode Views
class VoucherModeConfigListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = VoucherModeConfig
    template_name = 'forms_designer/voucher_config_list_modal.html'  # Use the new unified template
    context_object_name = 'configs'
    permission_required = ('accounting', 'vouchermodeconfig', 'view')
    
    def get_queryset(self):
        return VoucherModeConfig.objects.filter(organization_id=self.request.user.get_active_organization().id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:voucher_config_create')
        context['create_button_text'] = 'New Voucher Mode Config'
        context['page_title'] = 'Voucher Configurations'
        context['breadcrumbs'] = [
            ('Voucher Configurations', None),
        ]
        return context


class VoucherModeConfigDetailView(PermissionRequiredMixin, LoginRequiredMixin, DetailView):
    model = VoucherModeConfig
    template_name = 'accounting/voucher_config_detail.html'
    context_object_name = 'config'
    permission_required = ('accounting', 'vouchermodeconfig', 'view')

    def get_queryset(self):
        return VoucherModeConfig.objects.filter(organization_id=self.request.user.get_active_organization().id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Voucher Configuration Details: {self.object.name}',
            'page_title': f'Voucher Configuration Details: {self.object.name}',
            'breadcrumbs': [
                ('Voucher Configurations', reverse('accounting:voucher_config_list')),
                (f'Details: {self.object.name}', None)
            ]
        })
        return context


class VoucherEntryView(VoucherConfigMixin, PermissionRequiredMixin, LoginRequiredMixin, View):
    template_name = 'accounting/voucher_entry.html'
    permission_required = ('accounting', 'journal', 'add')
    config_pk_kwarg = "config_id"

    def get_user_perms(self, request):
        """
        Return a dict of user permissions for voucher actions.
        """
        organization = request.user.get_active_organization()
        return {
            "can_edit": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'),
            "can_add": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'),
            "can_delete": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'),
        }


    def _get_voucher_schema(self, config):
        schema, warning, _ = load_voucher_schema(config)
        if schema:
            schema = _inject_udfs_into_schema(schema, list(config.udf_configs.all()))
        return schema, warning

    def _create_voucher_forms(self, schema, organization, user_perms, request=None):
        header_schema = schema.get("header", {})
        lines_schema = schema.get("lines", {})

        HeaderForm = build_form(header_schema, organization=organization, user_perms=user_perms, prefix="header", model=Journal)
        LineFormSet = build_formset(lines_schema, organization=organization, user_perms=user_perms, model=JournalLine, prefix="lines")

        if request:
            header_form = HeaderForm(request.POST)
            line_formset = LineFormSet(request.POST)
        else:
            header_form = HeaderForm(initial={'journal_date': timezone.now().strftime('%Y-%m-%d')})
            line_formset = LineFormSet()
        
        return header_form, line_formset

    def get(self, request, *args, **kwargs):
        config_id = kwargs.get("config_id")
        warning = None
        config = None
        
        all_configs = VoucherModeConfig.objects.filter(is_active=True, archived_at__isnull=True)
        
        if not config_id:
            config = all_configs.first()
            if not config:
                return render(request, self.template_name, {
                    "page_title": "Voucher Entry",
                    "user_perms": self.get_user_perms(request),
                    "error": "No voucher configuration available.",
                    "voucher_configs": all_configs,
                })
            config_id = config.pk
        
        try:
            config = self.get_config()
        except Exception as e:
            warning = f"Voucher configuration not found: {e}"

        schema, schema_warning = self._get_voucher_schema(config)
        if schema_warning:
            warning = schema_warning

        if not schema:
            return render(request, self.template_name, {
                "error": warning or "Schema not found for this voucher type.",
                "user_perms": self.get_user_perms(request),
                "config": config,
                "voucher_configs": all_configs,
            })

        organization = request.user.get_active_organization()
        user_perms = self.get_user_perms(request)
        
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms)

        defaults = list(getattr(config, 'defaults', []).all())
        
        context = {
            "config": config,
            "header_form": header_form,
            "line_formset": line_formset,
            "user_perms": user_perms,
            "page_title": "Voucher Entry",
            "voucher_configs": all_configs,
            "defaults": defaults,
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        logger.debug(f"VoucherEntryView.post called by user={request.user} POST={request.POST}")
        
        try:
            config = self.get_config()
        except Exception as e:
            return render(request, self.template_name, {
                "error": f"Voucher configuration not found: {e}",
                "user_perms": self.get_user_perms(request),
            })

        schema, warning = self._get_voucher_schema(config)
        if not schema:
            return render(request, self.template_name, {
                "error": warning or "Schema not found for this voucher type.",
                "user_perms": self.get_user_perms(request),
                "config": config,
            })

        organization = request.user.get_active_organization()
        user_perms = self.get_user_perms(request)
        
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms, request=request)

        if header_form.is_valid() and line_formset.is_valid():
            header_data = header_form.cleaned_data
            lines_data = [f.cleaned_data for f in line_formset.forms if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]

            validation_service = JournalValidationService(organization)
            errors = validation_service.validate_journal_entry(header_data, lines_data)

            if not errors:
                with transaction.atomic():
                    try:
                        journal = create_voucher(
                            user=request.user,
                            config_id=config.pk,
                            header_data=header_data,
                            lines_data=lines_data,
                        )
                        messages.success(request, "Voucher created successfully.")
                        return redirect('accounting:journal_list')
                    except (JournalError, ValidationError) as e:
                        logger.error(
                            "Error creating voucher: %s", e,
                            exc_info=True,
                            extra={'user_id': request.user.pk, 'organization_id': request.organization.pk}
                        )
                        messages.error(request, f"Error creating voucher: {e}")
                    except Exception as e:
                        logger.exception(
                            "An unexpected error occurred while creating voucher: %s", e,
                            extra={'user_id': request.user.pk, 'organization_id': request.organization.pk}
                        )
                        messages.error(request, "An unexpected error occurred while creating the voucher.")
            else:
                if 'general' in errors:
                    for error in errors['general']:
                        header_form.add_error(None, error)
                if 'header' in errors:
                    for field, error in errors['header'].items():
                        header_form.add_error(field, error)
                if 'lines' in errors:
                    for error_info in errors['lines']:
                        index = error_info['index']
                        for field, error in error_info['errors'].items():
                            line_formset.forms[index].add_error(field, error)
                logger.warning(
                    "Voucher validation failed for user %s, organization %s. Errors: %s",
                    request.user.pk, request.organization.pk, errors,
                    extra={'user_id': request.user.pk, 'organization_id': request.organization.pk, 'validation_errors': errors}
                )
        else:
            logger.error(
                'Header form errors: %s, Line formset errors: %s for user %s, organization %s',
                header_form.errors, line_formset.errors, request.user.pk, request.organization.pk,
                extra={'user_id': request.user.pk, 'organization_id': request.organization.pk, 'header_errors': header_form.errors, 'line_errors': line_formset.errors}
            )
        
        context = {
            "config": config,
            "header_form": header_form,
            "line_formset": line_formset,
            "user_perms": user_perms,
            "page_title": "Voucher Entry",
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)



# Currency Views
class CurrencyListView(LoginRequiredMixin, ListView):
    model = Currency
    template_name = 'accounting/currency_list.html'
    context_object_name = 'currencies'
    paginate_by = 20

    def get_queryset(self):
        return Currency.objects.all().order_by('currency_code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:currency_create')
        context['create_button_text'] = 'New Currency'
        context['page_title'] = 'Currencies'
        context['breadcrumbs'] = [
            ('Currencies', None),
        ]
        return context

# Currency Exchange Rate Views
class CurrencyExchangeRateListView(LoginRequiredMixin, ListView):
    model = CurrencyExchangeRate
    template_name = 'accounting/currency_exchange_rate_list.html'
    context_object_name = 'exchange_rates'
    paginate_by = 20

    def get_queryset(self):
        return CurrencyExchangeRate.objects.filter(
            organization_id=self.request.user.organization.id
        ).select_related('from_currency', 'to_currency').order_by('-rate_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Exchange Rates'
        context['create_url'] = reverse('accounting:exchange_rate_create')
        context['create_button_text'] = 'New Exchange Rate'
        context['breadcrumbs'] = [
            ('Exchange Rates', None),
        ]
        return context

# Tax Authority Views
class TaxAuthorityListView(LoginRequiredMixin, ListView):
    model = TaxAuthority
    template_name = 'accounting/tax_authority_list.html'
    context_object_name = 'tax_authorities'
    paginate_by = 20

    def get_queryset(self):
        return TaxAuthority.objects.filter(
            organization_id=self.request.user.organization.id
        ).order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:tax_authority_create')
        context['create_button_text'] = 'New Tax Authority'
        context['page_title'] = 'Tax Authorities'
        context['breadcrumbs'] = [
            ('Tax Authorities', None),
        ]
        return context


class TaxTypeListView(LoginRequiredMixin, ListView):
    model = TaxType
    template_name = 'accounting/tax_type_list.html'
    context_object_name = 'tax_types'
    paginate_by = 20

    def get_queryset(self):
        return TaxType.objects.filter(
            organization_id=self.request.user.organization.id
        ).order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:tax_type_create')
        context['create_button_text'] = 'New Tax Type'
        context['page_title'] = 'Tax Types'
        context['breadcrumbs'] = [
            ('Tax Types', None),
        ]
        return context

# Project Views
class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'accounting/project_list.html'
    context_object_name = 'projects'
    paginate_by = 20

    def get_queryset(self):
        return Project.objects.filter(
            organization_id=self.request.user.organization.id
        ).order_by('code')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:project_create')
        context['create_button_text'] = 'New Project'
        context['page_title'] = 'Projects'
        context['breadcrumbs'] = [
            ('Projects', None),
        ]
        return context



class AccountingPeriodListView(UserOrganizationMixin, ListView):
    model = AccountingPeriod
    template_name = 'accounting/accounting_period_list.html'
    context_object_name = 'accounting_periods'
    paginate_by = 20

    def get_queryset(self):
        org = self.get_organization()
        if not org:
            return self.model.objects.none()
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = user.get_active_organization()
        context['create_url'] = reverse('accounting:accounting_period_create')
        context['create_button_text'] = 'New Accounting Period'
        context['page_title'] = 'Accounting Periods'
        return context


class AccountingPeriodDetailView(DetailView):
    model = AccountingPeriod
    template_name = 'accounting/accounting_period_detail.html'
    context_object_name = 'accounting_period'
    slug_field = 'period_id'
    slug_url_kwarg = 'period_id'

    def get_queryset(self):
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = self.object
        context['back_url'] = reverse('accounting:accounting_period_list')
        context['edit_url'] = reverse('accounting:accounting_period_update', args=[period.pk])
        context['delete_url'] = reverse('accounting:accounting_period_delete', args=[period.pk])
        context['close_url'] = reverse('accounting:accounting_period_close', args=[period.pk])
        return context


class FiscalYearDetailView(DetailView):
    model = FiscalYear
    template_name = 'accounting/fiscal_year_detail.html'
    context_object_name = 'fiscal_year'
    slug_field = 'fiscal_year_id'
    slug_url_kwarg = 'fiscal_year_id'

    def get_queryset(self):
        return super().get_queryset().filter(organization=self.request.user.organization)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fy = self.object
        context['back_url'] = reverse('accounting:fiscal_year_list')
        context['edit_url'] = reverse('accounting:fiscal_year_update', args=[fy.pk])
        context['delete_url'] = reverse('accounting:fiscal_year_delete', args=[fy.pk])
        context['close_url'] = reverse('accounting:fiscal_year_close', args=[fy.pk])
        return context


class AccountingPeriodCloseView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = ('accounting', 'accountingperiod', 'change')

    def post(self, request, period_id):
        period = get_object_or_404(
            AccountingPeriod,
            pk=period_id,
            fiscal_year__organization=request.user.organization,
        )
        try:
            close_period(period, request.user)
            messages.success(request, 'Accounting period closed successfully.')
        except (JournalError, ValidationError) as e:
            logger.error(
                "Error closing accounting period %s: %s", period.pk, e,
                exc_info=True,
                extra={'period_id': period.pk, 'user_id': request.user.pk, 'organization_id': request.organization.pk}
            )
            messages.error(request, str(e))
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while closing accounting period %s: %s", period.pk, e,
                extra={'period_id': period.pk, 'user_id': request.user.pk, 'organization_id': request.organization.pk}
            )
            messages.error(request, "An unexpected error occurred while closing the period.")
        return redirect('accounting:accounting_period_list')


class FiscalYearCloseView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = ('accounting', 'fiscalyear', 'change')

    def post(self, request, fiscal_year_id):
        fy = get_object_or_404(
            FiscalYear,
            pk=fiscal_year_id,
            organization=request.user.organization,
        )
        if fy.periods.filter(status='open').exists():
            messages.error(request, 'Cannot close fiscal year with open periods.')
            return redirect('accounting:fiscal_year_list')
        fy.status = 'closed'
        fy.closed_by = request.user
        fy.closed_at = timezone.now()
        fy.save()
        messages.success(request, 'Fiscal year closed successfully.')
        return redirect('accounting:fiscal_year_list')

class JournalTypeListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    model = JournalType
    template_name = 'accounting/journal_type_list.html'
    context_object_name = 'journal_types'
    paginate_by = 20
    permission_required = ('accounting', 'journaltype', 'view')
   
    def get_queryset(self):
        org = self.get_organization()
        if not org:
            return self.model.objects.none()
        return JournalType.objects.filter(organization=org).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['create_url'] = reverse('accounting:journal_type_create')
        context['create_button_text'] = 'New Journal Type'
        context['page_title'] = 'Journal Types'
        context['breadcrumbs'] = [
            ('Journal Types', None),
        ]
        return context


class JournalTypeDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = JournalType
    template_name = 'accounting/journal_type_detail.html'
    context_object_name = 'journal_type'
    slug_field = 'journal_type_id'
    slug_url_kwarg = 'journal_type_id'
    permission_required = ('accounting', 'journaltype', 'view')

    def get_queryset(self):
        return JournalType.objects.filter(organization=self.get_organization())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': f'Journal Type Details: {self.object.name}',
            'page_title': f'Journal Type Details: {self.object.name}',
            'breadcrumbs': [
                ('Journal Types', reverse('accounting:journal_type_list')),
                (f'Details: {self.object.name}', None)
            ]
        })
        return context


class JournalTypeCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    model = JournalType
    form_class = JournalTypeForm
    template_name = 'accounting/journal_type_form.html'
    success_url = reverse_lazy('accounting:journal_type_list')
    permission_required = ('accounting', 'journaltype', 'add')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.organization = self.request.user.get_active_organization()
        messages.success(self.request, "Journal type created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Create New Journal Type',
            'page_title': 'Create New Journal Type',
            'breadcrumbs': [
                ('Journal Types', reverse('accounting:journal_type_list')),
                ('Create New', None)
            ]
        })
        return context


class JournalTypeDeleteView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = ('accounting', 'journaltype', 'delete')
    
    def post(self, request, journal_type_id):
        journal_type = get_object_or_404(
            JournalType, 
            journal_type_id=journal_type_id,
            organization_id=request.user.get_active_organization().id
        )
        
        if journal_type.is_system_type:
            messages.error(request, "System journal types cannot be deleted.")
            return redirect('accounting:journal_type_list')
        
        # Check if there are any journals using this type
        if journal_type.journals.exists():
            messages.error(request, f"Cannot delete journal type '{journal_type.name}' because it has associated journals.")
            return redirect('accounting:journal_type_list')
        
        journal_type_name = journal_type.name
        journal_type.delete()
        messages.success(request, f"Journal type '{journal_type_name}' deleted successfully.")
        return redirect('accounting:journal_type_list')


class VoucherUDFConfigListView(PermissionRequiredMixin, LoginRequiredMixin, ListView):
    model = VoucherUDFConfig
    template_name = 'accounting/voucher_udf_list.html'
    context_object_name = 'udf_configs'
    permission_required = ('accounting', 'voucherudfconfig', 'view')
    
    def get_queryset(self):
        return VoucherUDFConfig.objects.filter(
            voucher_mode__organization_id=self.request.user.get_active_organization().id
        ).select_related('voucher_mode')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Voucher UDF Configurations',
            'breadcrumbs': [
                ('Voucher UDF Configurations', None),
            ]
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
                ('Voucher UDF Configurations', reverse('accounting:voucher_udf_list')),
                ('Create New', None)
            ]
        })
        return context


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
                ('Voucher UDF Configurations', reverse('accounting:voucher_udf_list')),
                (f'Update {self.object.display_name}', None)
            ]
        })
        return context

class VoucherUDFConfigDeleteView(PermissionRequiredMixin, LoginRequiredMixin, View):
    permission_required = ('accounting', 'voucherudfconfig', 'delete')
    
    def post(self, request, pk):
        udf_config = get_object_or_404(
            VoucherUDFConfig, 
            pk=pk, 
            voucher_mode__organization_id=request.user.get_active_organization().id
        )
        udf_name = udf_config.display_name
        udf_config.delete()
        messages.success(request, f"UDF configuration '{udf_name}' deleted successfully.")
        return redirect('accounting:voucher_udf_list')

def get_next_account_code(request):
    org_id = request.GET.get("organization")
    parent_id = request.GET.get("parent_account")
    account_type = request.GET.get("account_type")
    if not org_id or org_id == "undefined":
        return JsonResponse({"error": "Missing or invalid organization"}, status=400)
    if not parent_id and not account_type:
        return JsonResponse({"next_code": ""})  # Don't try to look up if both are empty
    if account_type == "":
        account_type = None
    if parent_id == "":
        parent_id = None
    try:
        next_code = ChartOfAccount.get_next_code(org_id, parent_id, account_type)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"next_code": next_code})

# This part seems to be a part of a view function
def get_next_account_code_view(self, request):
    try:
        root_prefix = self.request.GET.get('root_prefix')
        org_id = self.request.GET.get('org_id')
        step = self.request.GET.get('step')  # Assuming step is passed as a GET parameter

        if not all([root_prefix, org_id, step]):
            return JsonResponse({'error': 'root_prefix, org_id, and step are required'}, status=400)

        max_code = self.get_next_account_code(root_prefix, org_id)

        if max_code >= int(root_prefix):
            next_code = str(max_code + int(step)).zfill(len(root_prefix))
        else:
            next_code = root_prefix

        return JsonResponse({'next_code': next_code})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

class ChartOfAccountFormFieldsView(LoginRequiredMixin, View):
    """HTMX view for dynamic form fields."""
    template_name = "accounting/chart_of_accounts_form_fields.html"

    @method_decorator(require_htmx)
    def get(self, request, *args, **kwargs):
        form = ChartOfAccountForm(organization=request.user.organization)
        return render(request, self.template_name, {'form': form})

@login_required
@csrf_exempt
def chart_of_accounts_create(request):
    initial = get_pending_form_initial(request)
    clear_storage_script = None
    org = getattr(request.user, 'organization', None)
    if request.method == 'POST':
        form = ChartOfAccountForm(request.POST, organization=org)
        # Ensure organization is set on the instance before validation
        if org is not None:
            form.instance.organization = org
        if form.is_valid():
            form.save()
            clear_pending_form(request)
            clear_storage_script = """
            <script>
            document.body.dispatchEvent(new Event('clearFormStorage'));
            </script>
            """
            # HTMX-aware redirect
            if request.headers.get('HX-Request'):
                from django.http import HttpResponse
                response = HttpResponse()
                response['HX-Redirect'] = reverse('accounting:chart_of_accounts_list')
                response['HX-Trigger'] = 'clearFormStorage'
                return response
            else:
                response = redirect('accounting:chart_of_accounts_list')
                response['HX-Trigger'] = 'clearFormStorage'
                return response
    else:
        form = ChartOfAccountForm(initial=initial, organization=org)
    context = {'form': form, 'form_post_url': request.path}
    if clear_storage_script:
        context['clear_storage_script'] = clear_storage_script
    return render(request, 'accounting/chart_of_accounts_form.html', context)

# Financial Reports Views
def get_trial_balance(organization, fiscal_year):
    """Return trial balance data for an organization and fiscal year."""
    accounts = ChartOfAccount.objects.filter(organization=organization, is_active=True).values("account_id", "account_code", "account_name").order_by("account_code")
    gl_totals = GeneralLedger.objects.filter(
        organization_id=organization.id,
        period__fiscal_year=fiscal_year,
        is_archived=False,
    ).values("account_id").annotate(
        debit_total=Sum("debit_amount"),
        credit_total=Sum("credit_amount"),
    )
    totals_map = {row["account_id"]: row for row in gl_totals}
    results = []
    for account in accounts:
        totals = totals_map.get(account["account_id"], {})
        debit = totals.get("debit_total") or Decimal("0")
        credit = totals.get("credit_total") or Decimal("0")
        balance = debit - credit
        results.append(
            {
                "account_id": account["account_id"],
                "account_code": account["account_code"],
                "account_name": account["account_name"],
                "debit_total": debit,
                "credit_total": credit,
                "balance": balance,
            }
        )
    return results

class TrialBalanceView(UserOrganizationMixin, TemplateView):
    """Display a trial balance for a selected fiscal year with CSV export."""

    template_name = "accounting/reports/trial_balance.html"

    def get(self, request, *args, **kwargs):
        """Return CSV if requested, otherwise render template."""
        if request.GET.get("format") == "csv":
            organization = self.get_organization()
            fiscal_year = self._get_selected_fiscal_year(organization)
            data = get_trial_balance(organization, fiscal_year) if fiscal_year else []

            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = "attachment; filename=trial_balance.csv"
            writer = csv.writer(response)
            writer.writerow(["Account Code", "Account Name", "Debit", "Credit", "Balance"])
            for row in data:
                writer.writerow([
                    row["account_code"],
                    row["account_name"],
                    row["debit_total"],
                    row["credit_total"],
                    row["balance"],
                ])
            return response

        return super().get(request, *args, **kwargs)

    def _get_selected_fiscal_year(self, organization):
        """Helper to fetch the fiscal year selected by the user."""
        fiscal_year_id = self.request.GET.get("fiscal_year")
        fiscal_year = None
        if fiscal_year_id:
            fiscal_year = FiscalYear.objects.filter(
                pk=fiscal_year_id, organization=organization
            ).first()
        if not fiscal_year:
            fiscal_year = FiscalYear.objects.filter(
                organization=organization, is_current=True
            ).first()
        return fiscal_year

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()

        if not organization:
            context["error"] = "No active organization found."
            return context

        fiscal_year = self._get_selected_fiscal_year(organization)
        trial_balance = (
            get_trial_balance(organization, fiscal_year) if fiscal_year else []
        )

        fiscal_years = FiscalYear.objects.filter(organization=organization).order_by(
            "-start_date"
        )

        context.update(
            {
                "organization": organization,
                "fiscal_year": fiscal_year,
                "fiscal_years": fiscal_years,
                "trial_balance": trial_balance,
                "page_title": "Trial Balance",
                "breadcrumbs": [("Reports", None), ("Trial Balance", None)],
            }
        )
        return context

class IncomeStatementView(UserOrganizationMixin, TemplateView):
    template_name = 'accounting/reports/income_statement.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        if not organization:
            context['error'] = 'No active organization found.'
            return context
        
        # Get period from request or use current period
        period_id = self.request.GET.get('period')
        if period_id:
            period = AccountingPeriod.objects.filter(
                id=period_id,
                fiscal_year__organization_id=organization.id
            ).first()
        else:
            period = AccountingPeriod.objects.filter(
                fiscal_year__organization_id=organization.id,
                is_current=True
            ).first()
        
        if not period:
            context['error'] = 'No accounting period found.'
            return context
        
        # Get income statement data
        income_statement = self.get_income_statement(organization, period)
        
        context.update({
            'organization': organization,
            'period': period,
            'income_statement': income_statement,
            'page_title': 'Income Statement',
            'breadcrumbs': [
                ('Reports', None),
                ('Income Statement', None),
            ]
        })
        
        return context
    
    def get_income_statement(self, organization, period):
        """Get income statement for the period"""
        # Get revenue accounts
        revenue_accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            account_type__nature='income',
            is_active=True
        )
        
        # Get expense accounts
        expense_accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            account_type__nature='expense',
            is_active=True
        )
        
        # Calculate revenue
        total_revenue = Decimal('0')
        revenue_details = []
        for account in revenue_accounts:
            credit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
            
            revenue_details.append({
                'account_name': account.account_name,
                'amount': credit_amount,
            })
            total_revenue += credit_amount
        
        # Calculate expenses
        total_expenses = Decimal('0')
        expense_details = []
        for account in expense_accounts:
            debit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            
            expense_details.append({
                'account_name': account.account_name,
                'amount': debit_amount,
            })
            total_expenses += debit_amount
        
        # Calculate net income
        net_income = total_revenue - total_expenses
        
        return {
            'revenue_details': revenue_details,
            'total_revenue': total_revenue,
            'expense_details': expense_details,
            'total_expenses': total_expenses,
            'net_income': net_income,
        }


class BalanceSheetView(LoginRequiredMixin, UserOrganizationMixin, TemplateView):
    template_name = 'accounting/reports/balance_sheet.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        if not organization:
            context['error'] = 'No active organization found.'
            return context
        
        # Get period from request or use current period
        period_id = self.request.GET.get('period')
        if period_id:
            period = AccountingPeriod.objects.filter(
                id=period_id,
                fiscal_year__organization_id=organization.id
            ).first()
        else:
            period = AccountingPeriod.objects.filter(
                fiscal_year__organization_id=organization.id,
                is_current=True
            ).first()
        
        if not period:
            context['error'] = 'No accounting period found.'
            return context
        
        # Get balance sheet data
        balance_sheet = self.get_balance_sheet(organization, period)
        
        context.update({
            'organization': organization,
            'period': period,
            'balance_sheet': balance_sheet,
            'page_title': 'Balance Sheet',
            'breadcrumbs': [
                ('Reports', None),
                ('Balance Sheet', None),
            ]
        })
        
        return context
    
    def get_balance_sheet(self, organization, period):
        """Get balance sheet for the period"""
        # Get asset accounts
        asset_accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            account_type__nature='asset',
            is_active=True
        )
        
        # Get liability accounts
        liability_accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            account_type__nature='liability',
            is_active=True
        )
        
        # Get equity accounts
        equity_accounts = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            account_type__nature='equity',
            is_active=True
        )
        
        # Calculate assets
        total_assets = Decimal('0')
        asset_details = []
        for account in asset_accounts:
            debit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            
            credit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
            
            balance = debit_amount - credit_amount
            
            asset_details.append({
                'account_name': account.account_name,
                'balance': balance,
            })
            total_assets += balance
        
        # Calculate liabilities
        total_liabilities = Decimal('0')
        liability_details = []
        for account in liability_accounts:
            debit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            
            credit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
            
            balance = credit_amount - debit_amount
            
            liability_details.append({
                'account_name': account.account_name,
                'balance': balance,
            })
            total_liabilities += balance
        
        # Calculate equity
        total_equity = Decimal('0')
        equity_details = []
        for account in equity_accounts:
            debit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0')
            
            credit_amount = GeneralLedger.objects.filter(
                organization_id=organization.id,
                period=period,
                account=account
            ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0')
            
            balance = credit_amount - debit_amount
            
            equity_details.append({
                'account_name': account.account_name,
                'balance': balance,
            })
            total_equity += balance
        
        return {
            'asset_details': asset_details,
            'total_assets': total_assets,
            'liability_details': liability_details,
            'total_liabilities': total_liabilities,
            'equity_details': equity_details,
            'total_equity': total_equity,
            'total_liabilities_equity': total_liabilities + total_equity,
        }


class ReportsListView(LoginRequiredMixin, UserOrganizationMixin, TemplateView):
    template_name = 'accounting/reports/reports_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        if not organization:
            context['error'] = 'No active organization found.'
            return context
        
        # Get available periods
        periods = AccountingPeriod.objects.filter(
            fiscal_year__organization_id=organization.id
        ).order_by('-start_date')
        
        context.update({
            'organization': organization,
            'periods': periods,
            'page_title': 'Financial Reports',
            'breadcrumbs': [
                ('Reports', None),
            ]
        })

        context['advanced_reports'] = build_report_cards()
        
        return context

@require_GET
def htmx_voucher_line(request):
    voucher_type = request.GET.get('type')
    index = request.GET.get('index', '0')
    organization = request.user.get_active_organization()
    user_perms = {
        "can_edit": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'),
        "can_add": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'),
        "can_delete": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'),
    }
    schema, _, _ = load_voucher_schema(VoucherModeConfig(code=voucher_type))
    if not schema or 'lines' not in schema:
        return render(request, 'accounting/vouchers/voucher_form_line_row.html', {
            'form': None,
            'index': index,
            'skeleton': True,
            'error': 'Schema not found or invalid.'
        })
    LineForm = build_form(schema['lines'], organization=organization, user_perms=user_perms, prefix=f'lines-{index}')
    form = LineForm(prefix=f'lines-{index}')
    return render(request, 'accounting/vouchers/voucher_form_line_row.html', {
        'form': form,
        'index': index,
        'skeleton': False,
    })

@csrf_exempt  # TODO: Replace with CSRF protection in production
@require_POST
def htmx_validate_voucher(request):
    """
    HTMX endpoint to validate voucher header and lines before save.
    Returns JSON: {valid: bool, errors: {header: {...}, lines: [...]}, toast_html: ...}
    """
    voucher_type = request.POST.get('type')
    organization = request.user.get_active_organization()
    user_perms = {
        "can_edit": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'),
        "can_add": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'),
        "can_delete": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'),
    }
    schema = load_schema(voucher_type)
    if not schema:
        return JsonResponse({"valid": False, "errors": {"schema": ["Schema not found."]}, "toast_html": "<div class='toast-error'>Schema not found.</div>"})
    # Build forms
    HeaderForm = build_form(schema.get("header", {}), organization=organization, user_perms=user_perms, prefix="header")
    header_form = HeaderForm(request.POST)
    LineFormSet = build_formset(schema.get("lines", {}), organization=organization, user_perms=user_perms, prefix="lines")
    line_formset = LineFormSet(request.POST)
    valid = header_form.is_valid() and line_formset.is_valid()
    errors = {
        "header": header_form.errors,
        "lines": [f.errors for f in line_formset.forms],
        "non_form_errors": line_formset.non_form_errors(),
    }
    # Render toast error block
    toast_html = ""
    if not valid:
        error_msgs = []
        for field, errs in header_form.errors.items():
            error_msgs.extend([f"Header: {field}: {e}" for e in errs])
        for i, form in enumerate(line_formset.forms):
            for field, errs in form.errors.items():
                error_msgs.extend([f"Line {i+1}: {field}: {e}" for e in errs])
        for e in line_formset.non_form_errors():
            error_msgs.append(f"Lines: {e}")
        toast_html = "<div class='toast-error'>" + "<br>".join(error_msgs) + "</div>"
    return JsonResponse({"valid": valid, "errors": errors, "toast_html": toast_html})

@require_GET
def htmx_lookup(request, model):
    """Generic HTMX lookup for various models."""
    query = request.GET.get('query', '')
    organization = request.user.get_active_organization()
    
    if model == 'accounts':
        objects = ChartOfAccount.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).filter(
            Q(account_code__icontains=query) | Q(account_name__icontains=query)
        )[:10]
        results = [{'id': obj.account_id, 'text': f"{obj.account_code} - {obj.account_name}"} for obj in objects]
    elif model == 'departments':
        objects = Department.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).filter(name__icontains=query)[:10]
        results = [{'id': obj.id, 'text': obj.name} for obj in objects]
    elif model == 'projects':
        objects = Project.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).filter(name__icontains=query)[:10]
        results = [{'id': obj.project_id, 'text': obj.name} for obj in objects]
    elif model == 'cost_centers':
        objects = CostCenter.objects.filter(
            organization_id=organization.id,
            is_active=True
        ).filter(name__icontains=query)[:10]
        results = [{'id': obj.cost_center_id, 'text': obj.name} for obj in objects]
    else:
        results = []
    
    return JsonResponse({'results': results})

# Journal Views (enhanced functionality)


class JournalDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """Detailed view of a journal entry."""
    model = Journal
    template_name = 'accounting/journal_detail.html'
    context_object_name = 'journal'
    permission_required = ('accounting', 'journal', 'view')
    
    def get_queryset(self):
        return Journal.objects.filter(
            organization_id=self.request.user.get_active_organization().id
        ).select_related(
            'journal_type', 'period', 'created_by', 'posted_by'
        ).prefetch_related('lines__account', 'lines__department', 'lines__project', 'lines__cost_center')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        context.update({
            'can_edit': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'change'),
            'can_delete': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'delete'),
            'can_post': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'post_journal'),
            'page_title': f'Journal Entry: {self.object.journal_number}',
            'breadcrumbs': [
                ('General Journal', reverse('accounting:journal_list')),
                (f'Entry: {self.object.journal_number}', None)
            ],
        })
        return context


class JournalEntryView(LoginRequiredMixin, UserOrganizationMixin, View):
    """Journal entry create/edit view with support for both new entries and editing existing ones."""
    template_name = 'accounting/journal_entry.html'
    
    def get(self, request, pk=None):
        organization = self.get_organization()
        
        if pk:
            journal = get_object_or_404(Journal, pk=pk, organization=organization)
            form = JournalForm(instance=journal, organization=organization)
            formset = JournalLineFormSet(instance=journal, prefix='lines')
            page_title = f'Edit Journal Entry #{journal.journal_number}'
        else:
            form = JournalForm(organization=organization)
            formset = JournalLineFormSet(prefix='lines')
            page_title = 'New Journal Entry'

        voucher_configs = VoucherModeConfig.objects.filter(organization=organization, is_active=True)
        selected_config_pk = request.GET.get('voucher_config', voucher_configs.first().pk if voucher_configs else None)
        selected_config = get_object_or_404(VoucherModeConfig, pk=selected_config_pk) if selected_config_pk else None
            
        context = {
            'form': form,
            'formset': formset,
            'voucher_configs': voucher_configs,
            'selected_config': selected_config,
            'page_title': page_title,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk=None):
        organization = self.get_organization()
        
        if pk:
            journal = get_object_or_404(Journal, pk=pk, organization=organization)
            form = JournalForm(request.POST, instance=journal, organization=organization)
            formset = JournalLineFormSet(request.POST, instance=journal, prefix='lines')
        else:
            form = JournalForm(request.POST, organization=organization)
            formset = JournalLineFormSet(request.POST, prefix='lines')

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                journal = form.save(commit=False)
                if not pk:
                    journal.organization = organization
                    journal.created_by = request.user
                journal.updated_by = request.user
                journal.save()
                
                formset.instance = journal
                formset.save()
                
                # Update totals
                journal.update_totals()
                journal.save()

            messages.success(request, "Journal entry saved successfully.")
            return redirect('accounting:journal_detail', pk=journal.pk)
        
        page_title = 'New Journal Entry' if not pk else f'Edit Journal Entry #{journal.journal_number}'
        context = {
            'form': form,
            'formset': formset,
            'page_title': page_title,
        }
        return render(request, self.template_name, context)


class GeneralLedgerDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    model = GeneralLedger
    template_name = 'accounting/general_ledger_detail.html'
    context_object_name = 'gl_entry'
    permission_required = ('accounting', 'generalledger', 'view')

    def get_queryset(self):
        return GeneralLedger.objects.filter(
            organization_id=self.request.user.get_active_organization().id
        ).select_related(
            'account', 'journal', 'period', 'department', 'cost_center'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        context.update({
            'can_edit': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'generalledger', 'change'),
            'can_delete': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'generalledger', 'delete'),
            'page_title': f'General Ledger Entry: {self.object.gl_entry_id}',
            'breadcrumbs': [
                ('General Ledger', reverse('accounting:general_ledger_list')),
                (f'Entry: {self.object.gl_entry_id}', None)
            ],
        })
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
        """Build dynamic form based on journal type configuration."""
        from accounting.forms import JournalForm
        
        class DynamicJournalForm(JournalForm):
            class Meta(JournalForm.Meta):
                pass
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.journal_type = journal_type
                
                # Add UDF fields if configured
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
        """Create form field for UDF configuration."""
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
        
        # Set journal number
        journal_type = form.cleaned_data.get('journal_type')
        if journal_type:
            form.instance.journal_number = journal_type.get_next_journal_number()
        
        response = super().form_valid(form)
        
        # Handle journal lines
        lines_data = self.request.POST.getlist('lines')
        if lines_data:
            self.save_journal_lines(form.instance, lines_data)
        
        messages.success(self.request, "Journal entry created successfully.")
        return response
    
    def save_journal_lines(self, journal, lines_data):
        """Save journal lines from form data."""
        for i, line_data in enumerate(lines_data):
            if not line_data.strip():
                continue
                
            try:
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
        
        # Get journal types for selection
        journal_types = JournalType.objects.filter(
            organization_id=organization.id,
            is_active=True
        )
        
        # Get accounts for line items
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


@require_POST
@login_required
def journal_save_ajax(request):
    """AJAX endpoint for saving journal entries."""
    organization = request.user.get_active_organization()
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    form = JournalForm(request.POST, organization=organization)
    formset = JournalLineFormSet(request.POST, form_kwargs={'organization': organization})

    if form.is_valid() and formset.is_valid():
        with transaction.atomic():
            journal = form.save(commit=False)
            journal.organization = organization
            journal.created_by = request.user
            journal.save()

            formset.instance = journal
            formset.save()

            journal.update_totals()
            journal.save()

            return JsonResponse({
                'success': True,
                'journal_id': journal.journal_id,
                'journal_number': journal.journal_number,
                'message': 'Journal entry saved successfully'
            })
    else:
        errors = form.errors.as_json()
        errors.update(formset.errors.as_json())
        return JsonResponse({'error': errors}, status=400)


@require_GET
@login_required
def journal_load_ajax(request):
    """AJAX endpoint for loading journal entries with filtering."""
    organization = request.user.get_active_organization()
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'view'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        
        # Get filter parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        account_filter = request.GET.get('account_id')
        status_filter = request.GET.get('status')
        
        # Build queryset
        queryset = Journal.objects.filter(
            organization_id=organization.id
        ).select_related(
            'journal_type', 'period', 'created_by'
        ).prefetch_related(
            'lines__account', 'lines__department', 'lines__project', 'lines__cost_center'
        )
        
        # Apply filters
        if start_date:
            queryset = queryset.filter(journal_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(journal_date__lte=end_date)
        if account_filter:
            queryset = queryset.filter(lines__account_id=account_filter).distinct()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Order and limit
        journals = queryset.order_by('-journal_date', '-journal_number')[:100]
        
        # Serialize data
        entries = []
        for journal in journals:
            journal_data = {
                'journal_id': journal.journal_id,
                'journal_number': journal.journal_number,
                'journal_date': journal.journal_date.isoformat(),
                'reference': journal.reference or '',
                'description': journal.description or '',
                'status': journal.status,
                'total_debit': float(journal.total_debit),
                'total_credit': float(journal.total_credit),
                'created_by': journal.created_by.get_full_name() if journal.created_by else '',
                'lines': []
            }
            
            for line in journal.lines.all():
                line_data = {
                    'account_code': line.account.account_code,
                    'account_name': line.account.account_name,
                    'description': line.description or '',
                    'debit_amount': float(line.debit_amount),
                    'credit_amount': float(line.credit_amount),
                    'department': line.department.name if line.department else '',
                    'project': line.project.name if line.project else '',
                    'cost_center': line.cost_center.name if line.cost_center else '',
                }
                journal_data['lines'].append(line_data)
            
            entries.append(journal_data)
        
        return JsonResponse({
            'success': True,
            'entries': entries,
            'total_count': len(entries)
        })
        
    except Exception as e:
        logger.error(f"Error loading journal entries: {e}")
        return JsonResponse({'error': 'An error occurred while loading entries'}, status=500)


@require_POST
@login_required
def journal_post_ajax(request):
    """AJAX endpoint for posting journal entries."""
    organization = request.user.get_active_organization()
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'post_journal'):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        journal_id = data.get('journal_id')

        journal = Journal.objects.get(
            journal_id=journal_id,
            organization_id=organization.id
        )
 
        post_journal(journal, request.user)
 
        return JsonResponse({
            'success': True,
            'message': 'Journal entry posted successfully'
        })
 
    except Journal.DoesNotExist:
        logger.warning(
            "Attempted to post non-existent journal_id=%s for user %s, organization %s",
            journal_id, request.user.pk, request.user.get_active_organization().pk,
            extra={'journal_id': journal_id, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk}
        )
        return JsonResponse({'error': 'Journal entry not found'}, status=404)
    except (JournalPostingError, JournalValidationError) as e:
        logger.error(
            "Journal posting failed for journal_id=%s: %s", journal_id, e,
            exc_info=True,
            extra={'journal_id': journal_id, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk, 'error_message': str(e)}
        )
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.exception(
            "An unexpected error occurred while posting journal entry_id=%s: %s", journal_id, e,
            extra={'journal_id': journal_id, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk}
        )
        return JsonResponse({'error': 'An unexpected error occurred while posting the entry'}, status=500)


@require_POST
@login_required
def journal_delete_ajax(request):
    """AJAX endpoint for deleting journal entries."""
    organization = request.user.get_active_organization()
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        journal_id = data.get('journal_id')
        
        journal = Journal.objects.get(
            journal_id=journal_id,
            organization_id=request.user.get_active_organization().id
        )
        
        if journal.status != 'draft':
            return JsonResponse({'error': 'Only draft entries can be deleted'}, status=400)
        
        journal.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Journal entry deleted successfully'
        })
        
    except Journal.DoesNotExist:
        logger.warning(
            "Attempted to delete non-existent journal_id=%s for user %s, organization %s",
            journal_id, request.user.pk, request.user.get_active_organization().pk,
            extra={'journal_id': journal_id, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk}
        )
        return JsonResponse({'error': 'Journal entry not found'}, status=404)
    except Exception as e:
        logger.exception(
            "An unexpected error occurred while deleting journal entry_id=%s: %s", journal_id, e,
            extra={'journal_id': journal_id, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk}
        )
        return JsonResponse({'error': 'An error occurred while deleting the entry'}, status=500)

@require_POST
@login_required
def htmx_delete_journal_line(request):
    line_id = request.POST.get('line_id')
    if not line_id:
        return JsonResponse({'error': 'No line_id provided.'}, status=400)
    try:
        line = JournalLine.objects.get(pk=line_id)
        # Permission check: only allow delete if user has permission
        organization = request.user.get_active_organization()
        if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'):
            from django.http import HttpResponse
            return HttpResponse('<tr><td colspan="100%"><div class="alert alert-danger">No permission to delete journal line.</div></td></tr>', status=403)
        line.delete()
        from django.http import HttpResponse
        return HttpResponse('', status=204)  # HTMX will remove the row
    except JournalLine.DoesNotExist:
        from django.http import HttpResponse
        return HttpResponse('<tr><td colspan="100%"><div class="alert alert-danger">Line not found.</div></td></tr>', status=404)

class VoucherModeConfigCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
    model = VoucherModeConfig
    form_class = VoucherModeConfigForm
    template_name = 'forms_designer/voucher_config_form.html'
    permission_required = ('accounting', 'vouchermodeconfig', 'add')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.request.user.get_active_organization()
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
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
                ('Create', None)
            ]
        })
        return context

class VoucherTypeConfigurationView(LoginRequiredMixin, View):
   def get(self, request, config_id):
       try:
           config = VoucherModeConfig.objects.get(pk=config_id, organization=request.user.get_active_organization())
           data = {
               'default_ledger_id': config.default_ledger.pk if config.default_ledger else None,
               'default_narration_template': config.default_narration_template,
               'default_voucher_mode': config.default_voucher_mode,
               'default_cost_center_id': config.default_cost_center.pk if config.default_cost_center else None,
               'default_tax_ledger_id': config.default_tax_ledger.pk if config.default_tax_ledger else None,
           }
           return JsonResponse(data)
       except VoucherModeConfig.DoesNotExist:
          return JsonResponse({'error': 'Configuration not found'}, status=404)

class VoucherConfigHXView(VoucherConfigListHXView):
   pass

class VoucherTypeConfigurationView(LoginRequiredMixin, View):
   def get(self, request, config_id):
       try:
           config = VoucherModeConfig.objects.get(pk=config_id, organization=request.user.get_active_organization())
           data = {
               'default_ledger_id': config.default_ledger.pk if config.default_ledger else None,
               'default_narration_template': config.default_narration_template,
               'default_voucher_mode': config.default_voucher_mode,
               'default_cost_center_id': config.default_cost_center.pk if config.default_cost_center else None,
               'default_tax_ledger_id': config.default_tax_ledger.pk if config.default_tax_ledger else None,
           }
           return JsonResponse(data)
       except VoucherModeConfig.DoesNotExist:
           return JsonResponse({'error': 'Configuration not found'}, status=404)

class JournalPostView(LoginRequiredMixin, View):
   def get(self, request, pk):
       journal = get_object_or_404(Journal, pk=pk, organization=request.user.get_active_organization())
       if journal.status != 'draft':
           messages.error(request, "Only draft journals can be posted.")
           return redirect('accounting:journal_detail', pk=pk)

       try:
           # Use the service function for posting to centralize logic and error handling
           from accounting.services import post_journal as service_post_journal
           journal = service_post_journal(journal)
           messages.success(request, "Journal posted successfully.")
           return redirect('accounting:journal_detail', pk=pk)
       except (JournalPostingError, JournalValidationError) as e:
           logger.error(
               "Journal posting failed for journal_id=%s: %s", journal.pk, e,
               exc_info=True,
               extra={'journal_id': journal.pk, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk, 'error_message': str(e)}
           )
           messages.error(request, str(e))
           return redirect('accounting:journal_detail', pk=pk)
       except Exception as e:
           logger.exception(
               "An unexpected error occurred while posting journal_id=%s: %s", journal.pk, e,
               extra={'journal_id': journal.pk, 'user_id': request.user.pk, 'organization_id': request.user.get_active_organization().pk}
           )
           messages.error(request, "An unexpected error occurred while posting the journal.")
           return redirect('accounting:journal_detail', pk=pk)
