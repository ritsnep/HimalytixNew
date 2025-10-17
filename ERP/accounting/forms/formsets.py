"""
Voucher Formsets - Properly configured formsets for journal entry management.

This module defines formset configurations for:
- JournalLineFormSet: Inline formset for managing multiple journal lines
- Additional formsets for other related models as needed
"""

import logging
from django.forms import BaseFormSet
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from accounting.forms.journal_line_form import JournalLineForm
from accounting.models import Journal, JournalLine

logger = logging.getLogger(__name__)


class VoucherLineBaseFormSet(BaseFormSet):
    """
    Custom base formset for journal lines with business logic validation.

    Validates:
    - At least one line exists
    - No duplicate line numbers
    - Total debits equal total credits
    - All required fields are present
    """

    def clean(self):
        """
        Perform formset-level validation.

        Raises:
            ValidationError: If validation fails
        """
        super().clean()

        if self.total_form_count() == 0:
            raise ValidationError(
                _('At least one journal line is required.'),
                code='no_lines'
            )

        # Track line numbers and amounts
        line_numbers = set()
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        deleted_count = 0

        for i, form in enumerate(self.forms):
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                # Check for deleted forms
                pass
            elif form.cleaned_data.get('DELETE'):
                deleted_count += 1
                continue

            # Skip empty forms
            if not form.cleaned_data:
                continue

            # Validate line number uniqueness
            line_number = form.cleaned_data.get('line_number')
            if line_number:
                if line_number in line_numbers:
                    form.add_error('line_number', _('Duplicate line number.'))
                line_numbers.add(line_number)

            # Sum debit and credit amounts
            debit = Decimal(str(form.cleaned_data.get('debit_amount') or 0))
            credit = Decimal(str(form.cleaned_data.get('credit_amount') or 0))
            total_debit += debit
            total_credit += credit

        # After deletions, must have at least one line
        active_lines = self.total_form_count() - deleted_count
        if active_lines < 1:
            raise ValidationError(
                _('At least one journal line must remain after deletions.'),
                code='min_lines_required'
            )

        # Check balance
        if total_debit != total_credit:
            balance_diff = abs(total_debit - total_credit)
            raise ValidationError(
                _('Journal must be balanced. '
                  'Total Debit: %(debit)s, Total Credit: %(credit)s. '
                  'Difference: %(diff)s') % {
                    'debit': total_debit,
                    'credit': total_credit,
                    'diff': balance_diff
                },
                code='unbalanced_journal'
            )

        logger.debug(
            f"Formset validation: {self.total_form_count()} forms, "
            f"debit={total_debit}, credit={total_credit}"
        )


# Import the inlineformset_factory and customize it
from django.forms import inlineformset_factory

# Create the base inline formset
_JournalLineFormSetBase = inlineformset_factory(
    parent_model=Journal,
    model=JournalLine,
    form=JournalLineForm,
    formset=VoucherLineBaseFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
    fields=[
        'account', 'description', 'debit_amount', 'credit_amount',
        'currency_code', 'exchange_rate', 'department', 'project',
        'cost_center', 'tax_code', 'tax_rate', 'tax_amount', 'memo'
    ]
)


class JournalLineFormSet(_JournalLineFormSetBase):
    """
    Customized inline formset for JournalLine with enhanced validation.

    Features:
    - Ensures balanced journal entries (debits = credits)
    - Validates minimum one line requirement
    - Prevents duplicate line numbers
    - Tracks deleted lines properly
    - Provides detailed error messages
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize formset with organization context.

        Args:
            form_kwargs: Dictionary containing 'organization' for form initialization
        """
        # Ensure form_kwargs includes organization
        form_kwargs = kwargs.get('form_kwargs', {})
        if 'organization' not in form_kwargs:
            logger.warning("JournalLineFormSet initialized without organization context")

        super().__init__(*args, **kwargs)

        # Auto-increment line numbers on initialization
        self._set_line_numbers()

    def _set_line_numbers(self):
        """
        Auto-assign line numbers to all forms.

        Line numbers are 10, 20, 30, etc. for easy insertion of new lines.
        """
        for idx, form in enumerate(self.forms):
            if form.instance.pk is None:  # Only for new lines
                form.instance.line_number = (idx + 1) * 10

    def get_totals(self):
        """
        Calculate and return totals for the formset.

        Returns:
            dict: {
                'total_debit': Decimal,
                'total_credit': Decimal,
                'balance': Decimal,
                'is_balanced': bool
            }
        """
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                debit = Decimal(str(form.cleaned_data.get('debit_amount') or 0))
                credit = Decimal(str(form.cleaned_data.get('credit_amount') or 0))
                total_debit += debit
                total_credit += credit

        return {
            'total_debit': total_debit,
            'total_credit': total_credit,
            'balance': total_debit - total_credit,
            'is_balanced': total_debit == total_credit
        }

    def get_non_deleted_forms(self):
        """
        Get all non-deleted forms in the formset.

        Returns:
            list: Forms that are not marked for deletion
        """
        return [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
