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
from accounting.models import VoucherConfiguration, AuditLog
from accounting.views.base_voucher_view import BaseVoucherView
from accounting.views.views_mixins import PermissionRequiredMixin

logger = logging.getLogger(__name__)


class GenericVoucherCreateView(PermissionRequiredMixin, BaseVoucherView):
    """
    Generic view for creating vouchers using VoucherConfiguration.
    """
    template_name = 'accounting/generic_dynamic_voucher_entry.html'
    permission_required = ('accounting', 'voucher', 'add')

    def get_voucher_config(self) -> VoucherConfiguration:
        """Get the voucher configuration by code."""
        code = self.kwargs.get('voucher_code')
        organization = self.get_organization()
        return get_object_or_404(
            VoucherConfiguration,
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
        line_formset = self._instantiate_target(
            line_formset_cls,
            initial=config.default_lines if config.default_lines else None
        )

        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            is_create=True
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
                    target_org = organization or getattr(config, 'organization', None)
                    if target_org is not None and hasattr(voucher, 'organization_id') and not getattr(voucher, 'organization_id', None):
                        voucher.organization_id = getattr(target_org, 'pk', target_org)
                    if hasattr(voucher, 'created_by') and not getattr(voucher, 'created_by_id', None):
                        voucher.created_by = request.user
                    if hasattr(voucher, 'updated_by'):
                        voucher.updated_by = request.user
                    voucher.save()

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

        context = self.get_context_data(
            config=config,
            header_form=header_form,
            line_formset=line_formset,
            is_create=True
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
            VoucherConfiguration,
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
        configs = VoucherConfiguration.objects.filter(
            organization=organization,
            is_active=True
        ).order_by('module', 'name')

        context = self.get_context_data(configs=configs)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Select Voucher Type',
            'configs': kwargs.get('configs', []),
        })
        return context