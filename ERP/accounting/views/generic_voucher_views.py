"""
Generic Voucher Views - Cross-module voucher creation and editing.

This module provides views for creating and editing vouchers using
the generic VoucherConfiguration system.
"""

import logging
from typing import Dict, Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import View

from accounting.forms.form_factory import VoucherFormFactory
from accounting.models import VoucherConfiguration, AuditLog
from accounting.views.base_voucher_view import BaseVoucherView
from accounting.views.views_mixins import PermissionRequiredMixin

logger = logging.getLogger(__name__)


class GenericVoucherCreateView(PermissionRequiredMixin, BaseVoucherView):
    """
    Generic view for creating vouchers using VoucherConfiguration.
    """
    template_name = 'accounting/generic_voucher_form.html'
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
        header_form = VoucherFormFactory.get_generic_voucher_form(
            voucher_config=config,
            organization=organization
        )

        line_formset = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=config,
            organization=organization
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

        header_form = VoucherFormFactory.get_generic_voucher_form(
            voucher_config=config,
            organization=organization,
            data=request.POST,
            files=request.FILES
        )

        line_formset = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=config,
            organization=organization,
            data=request.POST,
            files=request.FILES
        )

        if header_form.is_valid() and line_formset.is_valid():
            try:
                with transaction.atomic():
                    # Save header
                    voucher = header_form.save()
                    
                    # Save lines
                    for form in line_formset:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            line = form.save(commit=False)
                            line.voucher = voucher  # Assuming FK to header
                            line.save()

                    # Log audit
                    AuditLog.objects.create(
                        user=request.user,
                        organization=organization,
                        action='create',
                        content_type=type(voucher),
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