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

from django.forms import ModelForm, BaseFormSet

from accounting.models import Journal, JournalLine
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

        return JournalLineForm(**form_kwargs)

    @staticmethod
    def get_journal_line_formset(
        organization: 'Organization',
        instance: Optional[Journal] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        **kwargs
    ) -> BaseFormSet:
        """
        Create and return a properly initialized JournalLineFormSet.

        Args:
            organization: The organization context
            instance: Parent Journal instance
            data: POST data for binding
            files: FILES data
            **kwargs: Additional formset kwargs

        Returns:
            BaseFormSet: Initialized formset with organization context

        Formset Configuration:
            - extra: 1 (one blank line for new entries)
            - can_delete: True (can remove lines)
            - form_kwargs: {'organization': organization}

        Example:
            >>> journal = Journal.objects.first()
            >>> formset = VoucherFormFactory.get_journal_line_formset(
            ...     organization=org,
            ...     instance=journal
            ... )
            >>> # Or with POST data:
            >>> formset = VoucherFormFactory.get_journal_line_formset(
            ...     organization=org,
            ...     instance=journal,
            ...     data=request.POST,
            ...     files=request.FILES
            ... )
        """
        formset_kwargs = {
            'form_kwargs': {'organization': organization},
            **kwargs
        }

        if instance:
            formset_kwargs['instance'] = instance

        if data is not None:
            formset_kwargs['data'] = data

        if files is not None:
            formset_kwargs['files'] = files

        logger.debug(
            f"Creating JournalLineFormSet for organization {organization.id} "
            f"(instance: {instance.id if instance else 'None'})"
        )

        return JournalLineFormSet(**formset_kwargs)

    @staticmethod
    def create_blank_line_form(
        organization: 'Organization',
        form_index: int,
        prefix: str = 'lines'
    ) -> JournalLineForm:
        """
        Create a blank line form for dynamic addition via HTMX.

        Args:
            organization: The organization context
            form_index: The index for this form in the formset
            prefix: The formset prefix (default: 'lines')

        Returns:
            JournalLineForm: A blank line form with proper prefix

        Note:
            Used by HTMX handlers to generate new line templates.
            The returned form will have prefix formatted as '{prefix}-{form_index}'
        """
        form_prefix = f'{prefix}-{form_index}'
        return VoucherFormFactory.get_journal_line_form(
            organization=organization,
            prefix=form_prefix
        )

    @staticmethod
    def validate_forms(
        journal_form: JournalForm,
        line_formset: BaseFormSet
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Validate both the journal form and line formset.

        Args:
            journal_form: The bound JournalForm
            line_formset: The bound JournalLineFormSet

        Returns:
            tuple: (is_valid: bool, errors: dict)
                - is_valid: True if both forms are valid
                - errors: Dictionary of all errors from both forms

        Example:
            >>> is_valid, errors = VoucherFormFactory.validate_forms(
            ...     journal_form, 
            ...     line_formset
            ... )
            >>> if not is_valid:
            ...     # Handle errors
            ...     print(errors)
        """
        journal_valid = journal_form.is_valid()
        formset_valid = line_formset.is_valid()

        errors = {}

        if not journal_valid:
            errors['journal'] = journal_form.errors

        if not formset_valid:
            errors['lines'] = [
                form.errors if form.errors else {}
                for form in line_formset.forms
            ]
            # Also include formset non-form errors
            if line_formset.non_form_errors():
                errors['formset'] = line_formset.non_form_errors()

        is_valid = journal_valid and formset_valid

        logger.debug(
            f"Form validation result: valid={is_valid}, "
            f"errors={bool(errors)}"
        )

        return is_valid, errors

    @staticmethod
    def get_initial_data(
        organization: 'Organization',
        journal_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get initial data dictionary for a new journal form.

        Args:
            organization: The organization context
            journal_type: Optional journal type to pre-select

        Returns:
            dict: Initial data for form fields

        Example:
            >>> initial = VoucherFormFactory.get_initial_data(org, journal_type='JNL')
            >>> form = VoucherFormFactory.get_journal_form(
            ...     org,
            ...     initial=initial
            ... )
        """
        from django.utils import timezone
        from accounting.models import AccountingPeriod, JournalType

        initial = {
            'journal_date': timezone.now().date(),
            'currency_code': 'USD',
            'exchange_rate': 1.0,
            'status': 'draft',
        }

        # If journal type specified, pre-select it
        if journal_type:
            try:
                jt = JournalType.objects.get(
                    code=journal_type,
                    organization=organization
                )
                initial['journal_type'] = jt.id
            except JournalType.DoesNotExist:
                logger.warning(f"Journal type {journal_type} not found")

        # Set current open period if available
        current_period = AccountingPeriod.objects.filter(
            organization=organization,
            is_current=True,
            status='open'
        ).first()
        if current_period:
            initial['period'] = current_period.id

        logger.debug(f"Generated initial data: {initial}")

        return initial
