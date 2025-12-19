"""
Generic Voucher Views - Cross-module voucher creation and editing.

This module provides views for creating and editing vouchers using
the generic VoucherConfiguration system.
"""

import inspect
import logging
from typing import Dict, Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from accounting.forms.form_factory import VoucherFormFactory
from accounting.forms_factory import build_form
from accounting.models import VoucherModeConfig, AuditLog  # Using VoucherModeConfig (existing table)
from accounting.views.base_voucher_view import BaseVoucherView
from accounting.views.views_mixins import PermissionRequiredMixin

logger = logging.getLogger(__name__)


class GenericVoucherCreateView(PermissionRequiredMixin, BaseVoucherView):
    """
    Generic view for creating vouchers using VoucherModeConfig.
    """
    template_name = 'accounting/generic_dynamic_voucher_entry.html'
    permission_required = ('accounting', 'voucher', 'add')

    def get_voucher_config(self) -> VoucherModeConfig:
        """Get the voucher configuration by code."""
        code = self.kwargs.get('voucher_code')
        organization = self.get_organization()
        return get_object_or_404(
            VoucherModeConfig,
            code=code,
            organization=organization,
            is_active=True
        )

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """Display empty voucher form."""
        config = self.get_voucher_config()
        organization = self.get_organization()

        # Create forms using generic factory
        header_form_cls = VoucherFormFactory.get_generic_voucher_form(
            voucher_config=config,
            organization=organization
        )

        line_formset_cls = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=config,
            organization=organization
        )

        header_form = self._instantiate_target(header_form_cls)
        # VoucherModeConfig doesn't have default_lines attribute, use getattr with fallback
        default_lines = getattr(config, 'default_lines', None)
        line_formset = self._instantiate_target(
            line_formset_cls,
            initial=default_lines if default_lines else None
        )

        # Determine line section title based on voucher type
        line_section_title = "Line Items"
        if config.code in ['VM08', 'VM-JV', 'VM-GJ']:  # Journal vouchers
            line_section_title = "Journal Lines"
        elif 'INV' in config.code.upper() or 'STOCK' in config.code.upper():
            line_section_title = "Inventory Items"
        elif config.name and 'receipt' in config.name.lower():
            line_section_title = "Receipt Items"
        elif config.name and 'invoice' in config.name.lower():
            line_section_title = "Invoice Items"
        elif config.name and ('purchase' in config.name.lower() or 'sales' in config.name.lower()):
            line_section_title = "Transaction Items"
        
        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            is_create=True,
            line_section_title=line_section_title
        )

        logger.debug(f"GenericVoucherCreateView GET - Config: {config.code}")

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """Handle form submission."""
        config = self.get_voucher_config()
        organization = self.get_organization()

        header_form_cls = VoucherFormFactory.get_generic_voucher_form(
            voucher_config=config,
            organization=organization
        )

        line_formset_cls = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=config,
            organization=organization
        )

        header_form = self._instantiate_target(
            header_form_cls,
            data=request.POST,
            files=request.FILES
        )

        line_formset = self._instantiate_target(
            line_formset_cls,
            data=request.POST,
            files=request.FILES
        )

        if header_form.is_valid() and line_formset.is_valid():
            try:
                with transaction.atomic():
                    # Save header
                    voucher = header_form.save(commit=False)
                    # Attach organization/user fields when present
                    try:
                        logger.debug(f"Header form produced instance type={type(voucher)}, attrs={list(getattr(voucher, '__dict__', {}).keys())}")
                        logger.debug(f"Voucher meta fields: {[f.name for f in voucher._meta.fields]}")
                        logger.debug(f"hasattr(created_by)={hasattr(voucher, 'created_by')}, hasattr(created_by_id)={hasattr(voucher, 'created_by_id')}")
                        logger.debug(f"Request user: pk={getattr(request.user, 'pk', None)}, username={getattr(request.user, 'username', None)}")
                    except Exception:
                        pass
                    target_org = organization or getattr(config, 'organization', None)
                    if target_org is not None and hasattr(voucher, 'organization_id') and not getattr(voucher, 'organization_id', None):
                        voucher.organization_id = getattr(target_org, 'pk', target_org)
                    
                    # Set journal_type from config if voucher is a Journal model
                    if hasattr(voucher, 'journal_type_id') and hasattr(config, 'journal_type_id'):
                        if config.journal_type_id and not getattr(voucher, 'journal_type_id', None):
                            voucher.journal_type_id = config.journal_type_id
                    
                    # Set period for Journal models
                    if hasattr(voucher, 'period_id') and not getattr(voucher, 'period_id', None):
                        from accounting.models import AccountingPeriod
                        period = AccountingPeriod.objects.filter(organization=target_org, is_closed=False).first()
                        if period:
                            voucher.period_id = period.period_id
                    
                    # Ensure created_by/updated_by are set for voucher types that require them.
                    # Some models may not expose attribute access for the related object until saved,
                    # so check the model fields explicitly and assign by id where possible.
                    try:
                        uid = getattr(request.user, 'pk', None) or getattr(request.user, 'id', None)
                        field_names = {f.name for f in getattr(voucher, '_meta', {}).fields}
                        if 'created_by' in field_names or 'created_by_id' in field_names:
                            voucher.created_by_id = uid
                            logger.debug(f"Assigned created_by_id on instance (field-based): created_by_id={getattr(voucher, 'created_by_id', None)}")
                        if 'updated_by' in field_names or 'updated_by_id' in field_names:
                            voucher.updated_by_id = uid
                            logger.debug(f"Assigned updated_by_id on instance (field-based): updated_by_id={getattr(voucher, 'updated_by_id', None)}")
                    except Exception:
                        # Fall back to object assignment if id assignment fails
                        try:
                            voucher.created_by = request.user
                        except Exception:
                            pass
                        try:
                            voucher.updated_by = request.user
                        except Exception:
                            pass
                    # Debug: log voucher fields before save to aid diagnostics
                    try:
                        try:
                            logger.debug(f"Voucher before save: {type(voucher)} attrs={getattr(voucher, '__dict__', {})}")
                            logger.debug(f"Voucher pre-save audit attrs: created_by_id={getattr(voucher, 'created_by_id', None)}, updated_by_id={getattr(voucher, 'updated_by_id', None)}")
                        except Exception:
                            pass
                        voucher.save()
                    except Exception as e:
                        # If save failed due to missing non-null audit fields, try to set and retry
                        try:
                            from django.db import IntegrityError
                            if isinstance(e, IntegrityError) and hasattr(voucher, 'created_by'):
                                try:
                                    voucher.created_by = request.user
                                    voucher.save()
                                except Exception:
                                    logger.exception("Retry save after setting created_by failed")
                            else:
                                raise
                        except Exception:
                            # Re-raise original exception if handling didn't resolve
                            logger.exception(f"Error saving voucher: {e}")
                            raise

                    # Determine how to attach lines to header
                    line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)
                    header_model = type(voucher)
                    parent_fk_name = None
                    try:
                        for field in line_model._meta.fields:
                            if isinstance(field, models.ForeignKey) and field.remote_field and field.remote_field.model is header_model:
                                parent_fk_name = field.name
                                break
                    except Exception:
                        parent_fk_name = None
                    
                    # Save lines
                    next_line_number = 1
                    for form in line_formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            line = form.save(commit=False)

                            if parent_fk_name:
                                setattr(line, parent_fk_name, voucher)

                            # Ensure line numbers exist for line models that require them
                            if hasattr(line, 'line_number') and not getattr(line, 'line_number', None):
                                setattr(line, 'line_number', next_line_number)
                                next_line_number += 1
                            line.save()

                    # Log audit
                    from django.contrib.contenttypes.models import ContentType
                    audit_org = organization or getattr(config, 'organization', None)
                    AuditLog.objects.create(
                        user=request.user,
                        organization=audit_org,
                        action='create',
                        content_type=ContentType.objects.get_for_model(voucher.__class__),
                        object_id=voucher.pk,
                        changes={'created': True},
                        details=f"Created {config.name} voucher"
                    )

                    messages.success(request, f"{config.name} created successfully.")
                    return redirect(self.get_success_url(voucher))

            except Exception as e:
                logger.exception(f"Error saving voucher: {e}")
                messages.error(request, "Error saving voucher.")
        else:
            messages.error(request, "Please correct the errors below.")

        # Determine line section title based on voucher type (same logic as GET)
        line_section_title = "Line Items"
        if config.code in ['VM08', 'VM-JV', 'VM-GJ']:  # Journal vouchers
            line_section_title = "Journal Lines"
        elif 'INV' in config.code.upper() or 'STOCK' in config.code.upper():
            line_section_title = "Inventory Items"
        elif config.name and 'receipt' in config.name.lower():
            line_section_title = "Receipt Items"
        elif config.name and 'invoice' in config.name.lower():
            line_section_title = "Invoice Items"
        elif config.name and ('purchase' in config.name.lower() or 'sales' in config.name.lower()):
            line_section_title = "Transaction Items"

        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            is_create=True,
            line_section_title=line_section_title
        )

        return self.render_to_response(context)

    def get_success_url(self, voucher):
        """Return URL to redirect after successful creation."""
        # This should be configurable based on the voucher type
        return reverse('accounting:voucher_list')

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build context for template."""
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': f"Create {kwargs.get('config').name}",
            'voucher_type': kwargs.get('config').code,
        })
        return context

    @staticmethod
    def _instantiate_target(target, data=None, files=None, **extra):
        """Helper that instantiates form/formset classes when needed."""
        if inspect.isclass(target):
            init_kwargs = {}
            if data is not None:
                init_kwargs['data'] = data
            if files is not None:
                init_kwargs['files'] = files
            for key, value in extra.items():
                if value is not None:
                    init_kwargs[key] = value
            return target(**init_kwargs)
        return target


class GenericVoucherLineView(PermissionRequiredMixin, BaseVoucherView):
    """HTMX endpoint that renders an additional line item for the generic voucher form."""

    permission_required = ('accounting', 'voucher', 'add')

    def get(self, request, *args, **kwargs) -> HttpResponse:
        voucher_code = request.GET.get('voucher_code')
        if not voucher_code:
            return HttpResponse("voucher_code parameter is required", status=400)

        organization = self.get_organization()
        config = get_object_or_404(
            VoucherModeConfig,
            code=voucher_code,
            organization=organization,
            is_active=True
        )

        index_value = request.GET.get('index', '0')
        try:
            line_index = max(0, int(index_value))
        except ValueError:
            line_index = 0

        lines_schema = (config.ui_schema or {}).get('lines', {})
        line_model = VoucherFormFactory._get_line_model_for_voucher_config(config)
        LineFormClass = build_form(
            lines_schema,
            model=line_model,
            organization=organization,
            prefix=f"lines-{line_index}"
        )

        form = LineFormClass()
        return render(request, 'accounting/partials/generic_dynamic_voucher_line_row.html', {
            'form': form,
            'index': line_index,
        })


class VoucherTypeSelectionView(PermissionRequiredMixin, BaseVoucherView):
    """
    View for selecting voucher type before creation.
    """
    template_name = 'accounting/voucher_type_selection.html'
    permission_required = ('accounting', 'voucher', 'add')

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """Display voucher type selection."""
        organization = self.get_organization()

        # Get all active voucher configurations
        configs = VoucherModeConfig.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('code')

        # Group configurations by journal type (since VoucherModeConfig doesn't have module field)
        configs_by_module = {'Accounting': list(configs)}

        context = self.get_context_data(configs=configs, configs_by_module=configs_by_module)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Select Voucher Type',
            'configs': kwargs.get('configs', []),
        })
        return context
