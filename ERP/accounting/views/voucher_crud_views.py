"""
Comprehensive CRUD Views for Voucher Entry System
Provides full Create, Read, Update, Delete functionality for journal vouchers
"""

import logging
from typing import Optional, Dict, Any
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum, Prefetch
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View

from accounting.models import (
    Journal, JournalLine, VoucherModeConfig, AccountingPeriod, 
    JournalType, ChartOfAccount
)
from accounting.forms_factory import build_form, build_formset
from accounting.schema_loader import load_voucher_schema
from accounting.services.create_voucher import create_voucher
from accounting.services.post_journal import (
    post_journal,
    JournalError,
    JournalValidationError,
    JournalPostingError,
)
from accounting.validation import JournalValidationService
from accounting.views.views_mixins import UserOrganizationMixin, PermissionRequiredMixin, VoucherConfigMixin
from usermanagement.utils import PermissionUtils

logger = logging.getLogger(__name__)


def _build_voucher_htmx_endpoints():
    return {
        "header": reverse('accounting:journal_entry_header_partial'),
        "lines": reverse('accounting:journal_entry_lines_partial'),
        "row": reverse('accounting:journal_entry_row'),
        "add_line": reverse('accounting:journal_entry_add_row'),
        "duplicate_line": reverse('accounting:journal_entry_row_duplicate'),
        "side_panel": reverse('accounting:journal_entry_side_panel'),
        "tax": reverse('accounting:voucher_entry_tax_calculation_hx'),
        "account_lookup": reverse('accounting:voucher_entry_account_lookup_hx'),
        "currency": reverse('accounting:resolve_exchange_rate'),
        "auto_balance": reverse('accounting:journal_entry_auto_balance'),
        "auto_date": reverse('accounting:voucher_entry_auto_date_hx'),
        "approval_actions": reverse('accounting:voucher_entry_approval_actions_hx'),
        "submit": reverse('accounting:journal_submit'),
        "save": reverse('accounting:journal_save_draft'),
        "approve": reverse('accounting:journal_approve'),
        "reject": reverse('accounting:journal_reject'),
        "post": reverse('accounting:journal_post'),
    }


def _inject_udfs_into_schema(schema, udf_configs):
    """Injects UDF configurations into the header and lines schema."""
    header_schema = schema.get("header", {})
    lines_schema = schema.get("lines", {})

    for udf in udf_configs:
        udf_schema = {
            "name": f"udf_{udf.field_name}",
            # display_name is the User-friendly label stored on VoucherUDFConfig
            "label": getattr(udf, "display_name", None) or getattr(udf, "field_label", udf.field_name),
            "type": udf.field_type,
            "required": udf.is_required,
            "choices": udf.choices or [],
        }
        if udf.scope == 'header':
            header_schema.setdefault('fields', []).append(udf_schema)
        elif udf.scope == 'line':
            lines_schema.setdefault('fields', []).append(udf_schema)
    return schema


class VoucherListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    """
    List all journal vouchers with filtering, search, and pagination.
    """
    model = Journal
    template_name = 'accounting/voucher_list.html'
    context_object_name = 'vouchers'
    permission_required = ('accounting', 'journal', 'view')
    paginate_by = 25

    def get_queryset(self):
        """Get filtered and sorted queryset."""
        queryset = super().get_queryset().select_related(
            'journal_type', 'period', 'created_by', 'posted_by', 'updated_by'
        ).prefetch_related('lines').order_by('-journal_date', '-created_at')

        # Search filter
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(journal_number__icontains=search) |
                Q(description__icontains=search) |
                Q(reference__icontains=search)
            )

        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Date range filter
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(journal_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(journal_date__lte=end_date)

        # Journal type filter
        journal_type = self.request.GET.get('journal_type')
        if journal_type:
            queryset = queryset.filter(journal_type_id=journal_type)

        return queryset

    def get_context_data(self, **kwargs):
        """Add context for filtering and actions."""
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        context.update({
            'page_title': 'Voucher Entries',
            'journal_types': JournalType.objects.filter(organization=organization),
            'statuses': Journal.STATUS_CHOICES,
            'can_create': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'add'),
            'can_edit': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'change'),
            'can_delete': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'delete'),
            'create_url': reverse('accounting:voucher_create'),
        })
        return context


class VoucherDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Display detailed view of a voucher in read-only mode.
    Shows all lines, UDFs, audit trail, and available actions.
    """
    model = Journal
    template_name = 'accounting/voucher_detail.html'
    context_object_name = 'voucher'
    permission_required = ('accounting', 'journal', 'view')

    def get_queryset(self):
        """Get journal with related data."""
        return super().get_queryset().select_related(
            'journal_type', 'period', 'created_by', 'posted_by', 'updated_by'
        ).prefetch_related(
            Prefetch('lines', queryset=JournalLine.objects.select_related(
                'account', 'department', 'project', 'cost_center'
            ).order_by('line_number'))
        )

    def get_context_data(self, **kwargs):
        """Build context with voucher data and actions."""
        context = super().get_context_data(**kwargs)
        voucher = self.object
        organization = self.get_organization()
        
        # Calculate totals
        lines = voucher.lines.all()
        total_debit = sum(line.debit_amount or 0 for line in lines)
        total_credit = sum(line.credit_amount or 0 for line in lines)
        
        context.update({
            'page_title': f'Voucher {voucher.journal_number}',
            'total_debit': total_debit,
            'total_credit': total_credit,
            'is_balanced': abs(total_debit - total_credit) < 0.01,
            'can_edit': (
                voucher.status == 'draft' and 
                PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'change')
            ),
            'can_delete': (
                voucher.status == 'draft' and 
                PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'delete')
            ),
            'can_post': (
                voucher.status == 'draft' and
                PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'post_journal')
            ),
            'edit_url': reverse('accounting:voucher_edit', kwargs={'pk': voucher.pk}),
            'delete_url': reverse('accounting:voucher_delete', kwargs={'pk': voucher.pk}),
            'post_url': reverse('accounting:voucher_post', kwargs={'pk': voucher.pk}),
            'list_url': reverse('accounting:voucher_list'),
        })
        return context


class VoucherCreateView(VoucherConfigMixin, PermissionRequiredMixin, LoginRequiredMixin, View):
    """
    Create a new journal voucher entry using dynamic form configuration.
    Supports both traditional and wizard-style entry.
    """
    template_name = 'accounting/voucher_entry_new.html'
    permission_required = ('accounting', 'journal', 'add')

    def get_user_perms(self, request):
        """Return user permissions for voucher actions."""
        organization = request.user.get_active_organization()
        return {
            "can_edit": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'),
            "can_add": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'),
            "can_delete": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'),
        }

    def _get_voucher_schema(self, config):
        """Load and inject UDFs into voucher schema."""
        schema, warning, _ = load_voucher_schema(config)
        if schema:
            schema = _inject_udfs_into_schema(schema, list(config.udf_configs.all()))
        return schema, warning

    def _create_voucher_forms(self, schema, organization, user_perms, request=None):
        """Create header form and line formset from schema."""
        header_schema = schema.get("header", {})
        lines_schema = schema.get("lines", {})

        HeaderForm = build_form(header_schema, organization=organization, 
                               user_perms=user_perms, prefix="header", model=Journal)
        LineFormSet = build_formset(lines_schema, organization=organization, 
                                   user_perms=user_perms, model=JournalLine, prefix="lines")

        if request:
            header_form = HeaderForm(request.POST)
            line_formset = LineFormSet(request.POST)
        else:
            header_form = HeaderForm(initial={'journal_date': timezone.now().strftime('%Y-%m-%d')})
            line_formset = LineFormSet()
        
        return header_form, line_formset

    def get(self, request, *args, **kwargs):
        """Display empty voucher entry form or config selection."""
        config_id = kwargs.get("config_id") or request.GET.get("config_id")
        warning = None
        config = None
        
        organization = request.user.get_active_organization()
        all_configs = VoucherModeConfig.objects.filter(
            is_active=True, 
            archived_at__isnull=True,
            organization=organization
        )
        
        # If no config_id provided, default to first and show modal if multiple
        show_config_modal = False
        if not config_id:
            if all_configs.count() == 0:
                messages.error(request, "No voucher configuration available. Please create one first.")
                return redirect('accounting:voucher_config_list')
            # Default to first config; if more than one exists, we'll prompt with a modal on the form
            config = all_configs.first()
            config_id = config.pk
            show_config_modal = all_configs.count() > 1
        
        try:
            config = get_object_or_404(VoucherModeConfig, pk=config_id, is_active=True, organization=organization)
        except Exception as e:
            warning = f"Voucher configuration not found: {e}"
            messages.error(request, warning)
            return redirect('accounting:voucher_list')

        schema, schema_warning = self._get_voucher_schema(config)
        if schema_warning:
            warning = schema_warning

        if not schema:
            messages.error(request, warning or "Schema not found for this voucher type.")
            return redirect('accounting:voucher_list')

        user_perms = self.get_user_perms(request)
        
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms)

        defaults = list(getattr(config, 'defaults', []).all())
        
        # Get all active accounts for the dropdown
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('account_code')
        
        context = {
            "config": config,
            "selected_config": config,  # Template expects selected_config
            "configs": all_configs,  # Template expects configs
            "header_form": header_form,
            "line_formset": line_formset,
            "user_perms": user_perms,
            "page_title": f"Create New Voucher - {config.name}",
            "voucher_configs": all_configs,
            "defaults": defaults,
            "accounts": accounts,
            "is_create": True,
            "is_edit": False,
            "form_action": reverse('accounting:voucher_create_with_config', kwargs={'config_id': config.pk}),
            "cancel_url": reverse('accounting:voucher_list'),
            "show_config_modal": show_config_modal,
            "voucher_entry_page": True,
            "initial_voucher_type": config.journal_type.name,
            "htmx_endpoints": _build_voucher_htmx_endpoints(),
            "initial_state": self._build_initial_state(config, organization),
            "lines": [],  # Empty lines for create view
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)

    def _build_initial_state(self, config, organization):
        """Build initial state for the new SPA voucher entry."""
        from accounting.models import VoucherUDFConfig
        
        # UDF definitions
        udf_header_defs = []
        udf_line_defs = []
        for udf in config.udf_configs.all():
            udf_def = {
                'id': udf.field_name,
                'label': getattr(udf, 'display_name', None) or udf.field_label,
                'type': udf.field_type,
                'required': udf.is_required,
                'options': udf.choices or [],
            }
            if udf.scope == 'header':
                udf_header_defs.append(udf_def)
            elif udf.scope == 'line':
                udf_line_defs.append(udf_def)
        
        # Numbering
        numbering = {
            'prefix': {'Sales': 'SI', 'Purchase': 'PI', 'Journal': 'JV'},
            'nextSeq': {'Sales': 1, 'Purchase': 1, 'Journal': 1},
            'width': 4,
        }
        
        # Default header
        header = {
            'party': '',
            'date': timezone.now().strftime('%Y-%m-%d'),
            'branch': 'Main',
            'currency': 'NPR',
            'exRate': 1,
            'creditDays': 0,
            'priceInclusiveTax': True,
        }
        
        return {
            'voucherType': config.journal_type.name,
            'status': 'Draft',
            'header': header,
            'notes': '',
            'collapsed': {'header': False, 'actions': False, 'notes': False, 'totals': False},
            'udfHeaderDefs': udf_header_defs,
            'udfLineDefs': udf_line_defs,
            'colPrefsByType': {},  # Can be loaded from user preferences later
            'rows': [],  # Start with empty rows
            'charges': [
                {'id': 'freight', 'label': 'Freight', 'mode': 'amount', 'value': 0, 'sign': 1},
                {'id': 'discount', 'label': 'Discount @ Bill', 'mode': 'percent', 'value': 0, 'sign': -1},
            ],
            'numbering': numbering,
            'focus': {'r': 0, 'c': 0},
            'showUdfModal': False,
            'udfScope': 'Header',
            'udfDraft': {'label': '', 'type': 'text', 'required': False, 'options': ''},
            'showColManager': False,
            'colManagerDraft': [],
            'showCharges': False,
            'htmxEndpoints': _build_voucher_htmx_endpoints(),
        }

    def post(self, request, *args, **kwargs):
        """Handle voucher creation form submission."""
        logger.debug(f"VoucherCreateView.post called by user={request.user}")
        
        config_id = kwargs.get("config_id") or request.POST.get("config_id")
        if not config_id:
            messages.error(request, "Voucher configuration is required.")
            return redirect('accounting:voucher_list')
        
        try:
            # Ensure config belongs to the user's organization to prevent cross-org access
            config = get_object_or_404(VoucherModeConfig, pk=config_id, is_active=True, organization=organization)
        except Exception as e:
            messages.error(request, f"Voucher configuration not found: {e}")
            return redirect('accounting:voucher_list')

        schema, warning = self._get_voucher_schema(config)
        if not schema:
            messages.error(request, warning or "Schema not found for this voucher type.")
            return redirect('accounting:voucher_list')

        organization = request.user.get_active_organization()
        user_perms = self.get_user_perms(request)
        
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms, request=request)

        if header_form.is_valid() and line_formset.is_valid():
            header_data = header_form.cleaned_data
            lines_data = [f.cleaned_data for f in line_formset.forms 
                         if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]

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
                        messages.success(request, f"Voucher {journal.journal_number} created successfully.")
                        return redirect('accounting:voucher_detail', pk=journal.pk)
                    except (JournalError, ValidationError) as e:
                        logger.error("Error creating voucher", exc_info=True, extra={
                            'error': str(e),
                            'user_id': getattr(request.user, 'pk', None),
                            'organization_id': getattr(organization, 'pk', None),
                            'config_id': getattr(config, 'pk', None)
                        })
                        messages.error(request, f"Error creating voucher: {e}")
                    except Exception as e:
                        logger.exception("Unexpected error creating voucher", extra={
                            'error': str(e),
                            'user_id': getattr(request.user, 'pk', None),
                            'organization_id': getattr(organization, 'pk', None),
                            'config_id': getattr(config, 'pk', None)
                        })
                        messages.error(request, "An unexpected error occurred while creating the voucher.")
            else:
                # Add validation errors to forms
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
        
        # Re-render form with errors
        all_configs = VoucherModeConfig.objects.filter(
            is_active=True,
            archived_at__isnull=True,
            organization=organization
        )
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('account_code')

        context = {
            "config": config,
            "selected_config": config,
            "configs": all_configs,
            "voucher_configs": all_configs,
            "header_form": header_form,
            "line_formset": line_formset,
            "user_perms": user_perms,
            "page_title": f"Create New Voucher - {config.name}",
            "is_create": True,
            "is_edit": False,
            "accounts": accounts,
            "form_action": reverse('accounting:voucher_create_with_config', kwargs={'config_id': config.pk}),
            "cancel_url": reverse('accounting:voucher_list'),
            "show_config_modal": False,
            "voucher_entry_page": True,
            "initial_voucher_type": config.journal_type.name,
            "htmx_endpoints": _build_voucher_htmx_endpoints(),
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)


class VoucherUpdateView(VoucherConfigMixin, PermissionRequiredMixin, LoginRequiredMixin, View):
    """
    Update an existing journal voucher.
    Only draft vouchers can be edited.
    """
    template_name = 'accounting/voucher_entry_new.html'
    permission_required = ('accounting', 'journal', 'change')

    def get_user_perms(self, request):
        """Return user permissions for voucher actions."""
        organization = request.user.get_active_organization()
        return {
            "can_edit": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'),
            "can_add": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'add'),
            "can_delete": PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'delete'),
        }

    def _get_voucher_schema(self, config):
        """Load and inject UDFs into voucher schema."""
        schema, warning, _ = load_voucher_schema(config)
        if schema:
            schema = _inject_udfs_into_schema(schema, list(config.udf_configs.all()))
        return schema, warning

    def _create_voucher_forms(self, schema, organization, user_perms, journal=None, request=None):
        """Create header form and line formset from schema with existing data."""
        header_schema = schema.get("header", {})
        lines_schema = schema.get("lines", {})

        HeaderForm = build_form(header_schema, organization=organization, 
                               user_perms=user_perms, prefix="header", model=Journal)
        LineFormSet = build_formset(lines_schema, organization=organization, 
                                   user_perms=user_perms, model=JournalLine, prefix="lines")

        if request:
            header_form = HeaderForm(request.POST, instance=journal)
            line_formset = LineFormSet(request.POST, queryset=journal.lines.all() if journal else JournalLine.objects.none())
        else:
            # Populate initial data from existing journal
            initial_data = {}
            if journal:
                initial_data = {
                    'journal_date': journal.journal_date,
                    'reference': journal.reference,
                    'description': journal.description,
                    'journal_type': journal.journal_type,
                    'period': journal.period,
                }
            header_form = HeaderForm(initial=initial_data, instance=journal)
            line_formset = LineFormSet(queryset=journal.lines.all() if journal else JournalLine.objects.none())
        
        return header_form, line_formset

    def get(self, request, *args, **kwargs):
        """Display voucher edit form with existing data."""
        pk = kwargs.get('pk')
        organization = request.user.get_active_organization()
        
        try:
            journal = get_object_or_404(Journal, pk=pk, organization=organization)
        except Exception as e:
            messages.error(request, f"Voucher not found: {e}")
            return redirect('accounting:voucher_list')

        # Check if voucher can be edited
        if journal.status not in ['draft']:
            messages.warning(request, f"Cannot edit a {journal.status} voucher. You can only view it.")
            return redirect('accounting:voucher_detail', pk=journal.pk)

        # Get the config from the journal's type or use default
        config = VoucherModeConfig.objects.filter(is_active=True, archived_at__isnull=True).first()
        
        schema, warning = self._get_voucher_schema(config)
        if not schema:
            messages.error(request, warning or "Schema not found for this voucher type.")
            return redirect('accounting:voucher_detail', pk=journal.pk)

        user_perms = self.get_user_perms(request)
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms, journal=journal)

        # Get all active accounts for the dropdown
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('account_code')

        context = {
            "config": config,
            "header_form": header_form,
            "line_formset": line_formset,
            "user_perms": user_perms,
            "page_title": f"Edit Voucher {journal.journal_number}",
            "voucher": journal,
            "accounts": accounts,
            "is_edit": True,
            "form_action": reverse('accounting:voucher_edit', kwargs={'pk': journal.pk}),
            "cancel_url": reverse('accounting:voucher_detail', kwargs={'pk': journal.pk}),
            "voucher_entry_page": True,
            "initial_voucher_type": journal.journal_type.name,
            "htmx_endpoints": _build_voucher_htmx_endpoints(),
        }
        if warning:
            context["warning"] = warning
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Handle voucher update form submission."""
        pk = kwargs.get('pk')
        organization = request.user.get_active_organization()
        
        try:
            journal = get_object_or_404(Journal, pk=pk, organization=organization)
        except Exception as e:
            messages.error(request, f"Voucher not found: {e}")
            return redirect('accounting:voucher_list')

        # Check if voucher can be edited
        if journal.status not in ['draft']:
            messages.error(request, f"Cannot edit a {journal.status} voucher.")
            return redirect('accounting:voucher_detail', pk=journal.pk)

        config = VoucherModeConfig.objects.filter(is_active=True, archived_at__isnull=True).first()
        schema, warning = self._get_voucher_schema(config)
        
        user_perms = self.get_user_perms(request)
        header_form, line_formset = self._create_voucher_forms(schema, organization, user_perms, journal=journal, request=request)

        if header_form.is_valid() and line_formset.is_valid():
            header_data = header_form.cleaned_data
            lines_data = [f.cleaned_data for f in line_formset.forms 
                         if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]

            validation_service = JournalValidationService(organization)
            errors = validation_service.validate_journal_entry(header_data, lines_data)

            if not errors:
                with transaction.atomic():
                    try:
                        # Update journal header
                        journal.journal_date = header_data.get('journal_date', journal.journal_date)
                        journal.reference = header_data.get('reference', journal.reference)
                        journal.description = header_data.get('description', journal.description)
                        journal.updated_by = request.user
                        journal.updated_at = timezone.now()
                        
                        # Delete existing lines
                        journal.lines.all().delete()
                        
                        # Create new lines
                        line_number = 1
                        for line_data in lines_data:
                            JournalLine.objects.create(
                                journal=journal,
                                line_number=line_number,
                                account=line_data.get('account'),
                                description=line_data.get('description', ''),
                                debit_amount=line_data.get('debit_amount', 0),
                                credit_amount=line_data.get('credit_amount', 0),
                                department=line_data.get('department'),
                                project=line_data.get('project'),
                                cost_center=line_data.get('cost_center'),
                                created_by=request.user,
                                updated_by=request.user,
                            )
                            line_number += 1
                        
                        # Update totals
                        journal.update_totals()
                        journal.save()
                        
                        messages.success(request, f"Voucher {journal.journal_number} updated successfully.")
                        return redirect('accounting:voucher_detail', pk=journal.pk)
                    except Exception as e:
                        logger.exception(f"Error updating voucher: {e}")
                        messages.error(request, f"Error updating voucher: {e}")
            else:
                # Add validation errors to forms
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
        
        # Re-render form with errors
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('account_code')

        context = {
            "config": config,
            "header_form": header_form,
            "line_formset": line_formset,
            "user_perms": user_perms,
            "page_title": f"Edit Voucher {journal.journal_number}",
            "voucher": journal,
            "accounts": accounts,
            "is_edit": True,
            "form_action": reverse('accounting:voucher_edit', kwargs={'pk': journal.pk}),
            "cancel_url": reverse('accounting:voucher_detail', kwargs={'pk': journal.pk}),
            "voucher_entry_page": True,
            "initial_voucher_type": journal.journal_type.name,
            "htmx_endpoints": _build_voucher_htmx_endpoints(),
        }
        return render(request, self.template_name, context)


class VoucherDeleteView(PermissionRequiredMixin, UserOrganizationMixin, DeleteView):
    """
    Delete a voucher (only if in draft status).
    """
    model = Journal
    template_name = 'accounting/voucher_confirm_delete.html'
    success_url = reverse_lazy('accounting:voucher_list')
    permission_required = ('accounting', 'journal', 'delete')
    context_object_name = 'voucher'

    def get_queryset(self):
        """Only draft vouchers can be deleted."""
        return super().get_queryset().filter(status='draft')

    def delete(self, request, *args, **kwargs):
        """Delete with additional validation."""
        voucher = self.get_object()
        
        if voucher.status != 'draft':
            messages.error(request, "Only draft vouchers can be deleted.")
            return redirect('accounting:voucher_detail', pk=voucher.pk)
        
        voucher_number = voucher.journal_number
        messages.success(request, f"Voucher {voucher_number} has been deleted.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add context for delete confirmation."""
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': f'Delete Voucher {self.object.journal_number}',
            'cancel_url': reverse('accounting:voucher_detail', kwargs={'pk': self.object.pk}),
        })
        return context


class VoucherPostView(PermissionRequiredMixin, UserOrganizationMixin, View):
    """
    Post a draft voucher to the general ledger.
    """
    permission_required = ('accounting', 'journal', 'post_journal')

    def post(self, request, *args, **kwargs):
        """Post the voucher."""
        pk = kwargs.get('pk')
        organization = request.user.get_active_organization()

        # Use a DB transaction and row locking to avoid concurrent posting
        try:
            with transaction.atomic():
                # Lock the voucher row for update
                voucher = Journal.objects.select_for_update().get(pk=pk, organization=organization)

                if voucher.status != 'draft':
                    messages.error(request, "Only draft vouchers can be posted.")
                    return redirect('accounting:voucher_detail', pk=voucher.pk)

                # Check accounting period still open for the voucher date
                try:
                    from accounting.models import AccountingPeriod
                    if not AccountingPeriod.is_date_in_open_period(organization, voucher.journal_date):
                        msg = "Voucher date is not in an open accounting period. Posting blocked."
                        logger.warning(msg, extra={
                            'voucher_id': voucher.pk,
                            'journal_date': str(voucher.journal_date),
                            'organization_id': getattr(organization, 'pk', None),
                            'user_id': getattr(request.user, 'pk', None)
                        })
                        messages.error(request, msg)
                        return redirect('accounting:voucher_detail', pk=voucher.pk)
                except Exception:
                    # If the helper isn't available, log and proceed cautiously
                    logger.exception('Failed to validate accounting period for voucher before posting', extra={
                        'voucher_id': pk,
                        'user_id': getattr(request.user, 'pk', None)
                    })

                # Attempt posting
                try:
                    post_journal(voucher, request.user)
                    messages.success(request, f"Voucher {voucher.journal_number} has been posted successfully.")
                except (JournalError, JournalValidationError, JournalPostingError) as e:
                    # Format a concise message for the user and log the details
                    try:
                        from accounting.services.post_journal import format_journal_exception
                        user_msg = format_journal_exception(e)
                    except Exception:
                        user_msg = str(e)

                    logger.error("Error posting voucher", exc_info=True, extra={
                        'voucher_id': voucher.pk,
                        'user_id': getattr(request.user, 'pk', None),
                        'organization_id': getattr(organization, 'pk', None),
                        'error': user_msg
                    })
                    messages.error(request, f"Error posting voucher: {user_msg}")
                    return redirect('accounting:voucher_detail', pk=voucher.pk)

        except Journal.DoesNotExist:
            messages.error(request, "Voucher not found.")
            return redirect('accounting:voucher_list')
        except Exception as e:
            logger.exception("Unexpected error during voucher post transaction", extra={
                'voucher_id': pk,
                'user_id': getattr(request.user, 'pk', None)
            })
            messages.error(request, "An unexpected error occurred while posting the voucher.")
            return redirect('accounting:voucher_detail', pk=pk)

        return redirect('accounting:voucher_detail', pk=voucher.pk)


class VoucherDuplicateView(PermissionRequiredMixin, UserOrganizationMixin, View):
    """
    Duplicate an existing voucher as a new draft entry.
    """
    permission_required = ('accounting', 'journal', 'add')

    def post(self, request, *args, **kwargs):
        """Create a duplicate of the voucher."""
        pk = kwargs.get('pk')
        organization = request.user.get_active_organization()
        
        try:
            source_voucher = get_object_or_404(Journal, pk=pk, organization=organization)
        except Exception as e:
            messages.error(request, f"Voucher not found: {e}")
            return redirect('accounting:voucher_list')
        
        with transaction.atomic():
            # Create new voucher as copy
            new_voucher = Journal.objects.create(
                organization=organization,
                journal_type=source_voucher.journal_type,
                period=source_voucher.period,
                journal_date=timezone.now().date(),
                description=f"Copy of {source_voucher.description}",
                reference=source_voucher.reference,
                status='draft',
                created_by=request.user,
                updated_by=request.user,
            )
            
            # Copy all lines
            line_number = 1
            for line in source_voucher.lines.all():
                JournalLine.objects.create(
                    journal=new_voucher,
                    line_number=line_number,
                    account=line.account,
                    description=line.description,
                    debit_amount=line.debit_amount,
                    credit_amount=line.credit_amount,
                    department=line.department,
                    project=line.project,
                    cost_center=line.cost_center,
                    created_by=request.user,
                    updated_by=request.user,
                )
                line_number += 1
            
            # Update totals
            new_voucher.update_totals()
            new_voucher.save()
        
        messages.success(request, f"Voucher duplicated as {new_voucher.journal_number}")
        return redirect('accounting:voucher_edit', pk=new_voucher.pk)
