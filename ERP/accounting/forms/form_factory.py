"""
Voucher Form Factory - Factory for creating properly initialized forms and formsets.

This module provides the VoucherFormFactory class which handles:
- Creating JournalForm instances with organization context
- Creating JournalLineForm instances with organization context
- Creating JournalLineFormSet with proper configuration
- Ensuring consistent form initialization across the application
"""

import logging
from typing import Optional, Type, Any, Dict

from django import forms
from django.db import models
from django.forms import ModelForm, BaseFormSet

from usermanagement.models import Organization
from accounting.models import Journal, JournalLine,VoucherConfiguration
from accounting.forms.journal_form import JournalForm
from accounting.forms.journal_line_form import JournalLineForm, JournalLineFormSet

logger = logging.getLogger(__name__)


class VoucherFormFactory:
    """
    Factory for creating and initializing journal entry forms.

    This class ensures all forms are created with proper organization context,
    default values, and consistent validation rules.
    """

    @staticmethod
    def get_journal_form(
        organization: 'Organization',
        journal_type: Optional[str] = None,
        instance: Optional[Journal] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        **kwargs
    ) -> JournalForm:
        """
        Create and return a properly initialized JournalForm.

        Args:
            organization: The organization context for the form
            journal_type: Optional journal type to filter (e.g., 'JNL', 'CR', 'CD')
            instance: Journal instance for editing (None for create)
            data: POST data for binding (None for unbound form)
            files: FILES data for attachments
            **kwargs: Additional form kwargs

        Returns:
            JournalForm: Initialized form instance with organization context

        Example:
            >>> from usermanagement.models import Organization
            >>> org = Organization.objects.first()
            >>> form = VoucherFormFactory.get_journal_form(org)
            >>> # Or with data binding:
            >>> form = VoucherFormFactory.get_journal_form(
            ...     org,
            ...     data=request.POST,
            ...     files=request.FILES
            ... )
        """
        form_kwargs = {
            'organization': organization,
            'journal_type': journal_type,
            **kwargs
        }

        if instance:
            form_kwargs['instance'] = instance

        if data is not None:
            form_kwargs['data'] = data

        if files is not None:
            form_kwargs['files'] = files

        logger.debug(
            f"Creating JournalForm for organization {organization.id} "
            f"(instance: {instance.id if instance else 'None'})"
        )

        # If a VoucherModeConfig exists for this organization+journal_type,
        # include its ui_schema header as `ui_schema` so the form can apply
        # runtime overrides (labels, placeholders, hidden/disabled fields).
        try:
            from accounting.models import VoucherModeConfig
            if organization and journal_type:
                cfg = VoucherModeConfig.objects.filter(
                    organization=organization,
                    journal_type__code=journal_type
                ).first()
                if cfg:
                    ui = cfg.resolve_ui()
                    if isinstance(ui, dict) and 'header' in ui:
                        form_kwargs['ui_schema'] = ui['header']
        except Exception:
            # Don't fail form creation if config lookup errors; log and continue
            logger.exception("Failed to load VoucherModeConfig for form schema")

        return JournalForm(**form_kwargs)

    @staticmethod
    def get_journal_line_form(
        organization: 'Organization',
        instance: Optional[JournalLine] = None,
        data: Optional[Dict] = None,
        prefix: Optional[str] = None,
        **kwargs
    ) -> JournalLineForm:
        """
        Create and return a properly initialized JournalLineForm.

        Args:
            organization: The organization context for the form
            instance: JournalLine instance for editing (None for new line)
            data: POST data for binding
            prefix: Form prefix for formset management
            **kwargs: Additional form kwargs

        Returns:
            JournalLineForm: Initialized form instance

        Example:
            >>> form = VoucherFormFactory.get_journal_line_form(
            ...     organization=org,
            ...     prefix='lines-0'
            ... )
        """
        form_kwargs = {
            'organization': organization,
            **kwargs
        }

        if instance:
            form_kwargs['instance'] = instance

        if data is not None:
            form_kwargs['data'] = data

        if prefix:
            form_kwargs['prefix'] = prefix

        logger.debug(
            f"Creating JournalLineForm for organization {organization.id} "
            f"(prefix: {prefix}, instance: {instance.id if instance else 'None'})"
        )

        # Attach line-level ui_schema if a voucher config exists for this org
        try:
            from accounting.models import VoucherModeConfig
            if organization and kwargs.get('journal_type'):
                cfg = VoucherModeConfig.objects.filter(
                    organization=organization,
                    journal_type__code=kwargs.get('journal_type')
                ).first()
            elif organization and instance and getattr(instance, 'journal', None):
                # If instance has a parent journal, try its journal_type
                j_type = getattr(getattr(instance, 'journal', None), 'journal_type', None)
                cfg = VoucherModeConfig.objects.filter(organization=organization, journal_type=j_type).first()
            else:
                cfg = None
            if cfg:
                ui = cfg.resolve_ui()
                if isinstance(ui, dict) and 'lines' in ui:
                    form_kwargs['ui_schema'] = ui['lines']
        except Exception:
            logger.exception("Failed to load VoucherModeConfig for line form schema")

        return JournalLineForm(**form_kwargs)

    @staticmethod
    def get_generic_voucher_form(
        voucher_config: 'VoucherConfiguration',
        organization: 'Organization',
        instance: Optional[Any] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        **kwargs
    ) -> ModelForm:
        """
        Create a generic voucher form using VoucherConfiguration.

        Args:
            voucher_config: The VoucherConfiguration defining the form schema
            organization: The organization context
            instance: Optional model instance for editing
            data: POST data for binding
            files: FILES data for attachments
            **kwargs: Additional form kwargs

        Returns:
            A ModelForm instance configured for the voucher type
        """
        from accounting.forms_factory import build_form

        # Get the model class for this voucher config
        model_class = VoucherFormFactory._get_model_for_voucher_config(voucher_config)

        # Build the form using the schema
        prefix = kwargs.pop('prefix', 'header')
        form_kwargs = {
            'organization': organization,
            'prefix': prefix,
            **kwargs
        }
        
        if instance:
            form_kwargs['instance'] = instance
        if data is not None:
            form_kwargs['data'] = data
        if files is not None:
            form_kwargs['files'] = files

        # Use build_form to create the ModelForm
        form = build_form(voucher_config.ui_schema.get('header', []), model=model_class, **form_kwargs)

        return form

    @staticmethod
    def get_generic_voucher_formset(
        voucher_config: 'VoucherConfiguration',
        organization: 'Organization',
        instance: Optional[Any] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        **kwargs
    ) -> BaseFormSet:
        """
        Create a generic voucher formset using VoucherConfiguration.

        Args:
            voucher_config: The VoucherConfiguration defining the form schema
            organization: The organization context
            instance: Optional model instance for editing
            data: POST data for binding
            files: FILES data for attachments
            **kwargs: Additional formset kwargs

        Returns:
            A BaseFormSet instance configured for the voucher type
        """
        from accounting.forms_factory import build_formset

        # Get the line model class for this voucher config
        line_model_class = VoucherFormFactory._get_line_model_for_voucher_config(voucher_config)

        # Get the lines schema from voucher config
        lines_schema = voucher_config.ui_schema.get('lines', [])

        # Build formset kwargs
        prefix = kwargs.pop('prefix', 'lines')
        formset_kwargs = {
            'organization': organization,
            'prefix': prefix,
            **kwargs
        }

        if data is not None:
            formset_kwargs['data'] = data
        if files is not None:
            formset_kwargs['files'] = files
        # VoucherModeConfig doesn't have default_lines attribute, use getattr with fallback
        default_lines = getattr(voucher_config, 'default_lines', None)
        if not instance and default_lines and data is None:
            formset_kwargs.setdefault('initial', default_lines)

        # Build the formset
        FormSetClass = build_formset(lines_schema, model=line_model_class, **formset_kwargs)

        return FormSetClass

    @staticmethod
    def _get_model_for_voucher_config(voucher_config: 'VoucherConfiguration') -> models.Model:
        """Get the header model class for a voucher configuration."""
        from django.apps import apps
        
        # Map module and code to model classes
        # Since multiple configs can have same (module, code), we use module-based logic
        # For VoucherModeConfig (new model), default to accounting module
        module = getattr(voucher_config, 'module', 'accounting')
        
        if module == 'accounting':
            if voucher_config.code == 'sales-invoice-vm-si':
                return apps.get_model('accounting', 'SalesInvoice')
            return apps.get_model('accounting', 'Journal')
        elif module == 'purchasing':
            # Use the actual purchasing models so FK fields (vendor, product, tax, etc.) resolve correctly
            if voucher_config.code == 'purchase_order':
                return apps.get_model('purchasing', 'PurchaseOrder')
            elif voucher_config.code == 'purchase-invoice-vm-pi':
                return apps.get_model('accounting', 'PurchaseInvoice')
            else:
                return apps.get_model('purchasing', 'PurchaseOrder')
        elif module == 'sales':
            if voucher_config.code == 'sales_order':
                try:
                    return apps.get_model('sales', 'SalesOrder')
                except Exception:
                    return apps.get_model('accounting', 'Journal')
            elif voucher_config.code == 'sales-invoice-vm-si':
                return apps.get_model('accounting', 'SalesInvoice')
            else:
                try:
                    return apps.get_model('sales', 'SalesOrder')
                except Exception:
                    return apps.get_model('accounting', 'Journal')
        elif module == 'inventory':
            if 'adjustment' in voucher_config.code.lower() or voucher_config.code == 'VM08':
                try:
                    return apps.get_model('inventory', 'StockAdjustment')
                except Exception:
                    return apps.get_model('accounting', 'Journal')
            return apps.get_model('accounting', 'Journal')
        else:
            # Default fallback
            return apps.get_model('accounting', 'Journal')

    @staticmethod
    def _get_line_model_for_voucher_config(voucher_config: 'VoucherConfiguration') -> models.Model:
        """Get the line model class for a voucher configuration."""
        from django.apps import apps
        
        # Map module and code to line model classes
        # VoucherModeConfig doesn't have module attribute, default to 'accounting'
        module = getattr(voucher_config, 'module', 'accounting')
        code = voucher_config.code.upper() if voucher_config.code else ''
        
        # Special code-based mapping that overrides module (for backwards compatibility)
        # Inventory vouchers - use StockAdjustmentLine for now (proper models to be created later)
        if 'GR' in code or 'RECEIPT' in code.replace('-', '').replace('_', ''):
            try:
                return apps.get_model('inventory', 'StockAdjustmentLine')
            except Exception:
                pass
        
        # Module-based mapping
        if module == 'accounting':
            if voucher_config.code == 'sales-invoice-vm-si':
                return apps.get_model('accounting', 'SalesInvoiceLine')
            # Only use JournalLine for actual journal vouchers
            if code in ['VM08', 'VM-JV', 'VM-GJ'] or 'JOURNAL' in code:
                return apps.get_model('accounting', 'JournalLine')
            # For all other accounting vouchers, also use JournalLine for now
            return apps.get_model('accounting', 'JournalLine')
        elif module == 'purchasing':
            if voucher_config.code == 'purchase_order':
                return apps.get_model('purchasing', 'PurchaseOrderLine')
            elif voucher_config.code == 'purchase-invoice-vm-pi':
                return apps.get_model('accounting', 'PurchaseInvoiceLine')
            else:
                return apps.get_model('purchasing', 'PurchaseOrderLine')
        elif module == 'sales':
            if voucher_config.code == 'sales_order':
                try:
                    return apps.get_model('sales', 'SalesOrderLine')
                except Exception:
                    return apps.get_model('accounting', 'JournalLine')
            elif voucher_config.code == 'sales-invoice-vm-si':
                return apps.get_model('accounting', 'SalesInvoiceLine')
            else:
                try:
                    return apps.get_model('sales', 'SalesOrderLine')
                except Exception:
                    return apps.get_model('accounting', 'JournalLine')
        elif module == 'inventory':
            # All inventory transactions use StockAdjustmentLine for now
            try:
                return apps.get_model('inventory', 'StockAdjustmentLine')
            except Exception:
                return apps.get_model('accounting', 'JournalLine')
        else:
            # Default fallback - only for journal vouchers
            return apps.get_model('accounting', 'JournalLine')


def get_voucher_ui_header(organization, journal_type=None):
    """Return the header portion of a VoucherModeConfig.ui_schema if it exists.

    Fallbacks:
      1) If journal_type specified, find voucher config for organization+journal_type
      2) Else, pick `is_default` config for organization
      3) Else, return None
    """
    try:
        from accounting.models import VoucherModeConfig
        cfg = None
        if organization and journal_type:
            cfg = VoucherModeConfig.objects.filter(organization=organization, journal_type__code=journal_type).first()
        if not cfg and organization:
            cfg = VoucherModeConfig.objects.filter(organization=organization, is_default=True).first()
        if cfg:
            ui = cfg.resolve_ui()
            return ui.get('header') if isinstance(ui, dict) else None
    except Exception:
        pass
    return None
