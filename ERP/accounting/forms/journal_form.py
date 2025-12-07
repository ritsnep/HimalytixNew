"""
Journal Header Form - ModelForm for Journal model.

This form handles the journal header fields including:
- journal_type: Type of journal (GL, CR, CD, etc.)
- period: Accounting period
- journal_date: Date of the journal entry
- reference: Reference number
- description: Journal description
- currency_code: Currency for the entry
- exchange_rate: Exchange rate if multi-currency
- status: Current status (draft, posted, etc.)

The form includes validation for:
- Date must be within an open accounting period
- Period must be open for posting
- Currency must be valid and active
"""

import logging
from typing import Any, Dict, Optional

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounting.models import Journal, AccountingPeriod, JournalType, Currency
from accounting.forms_mixin import BootstrapFormMixin
from accounting.forms.udf_mixins import UDFFormMixin
from utils.calendars import CalendarMode
from utils.widgets import DualCalendarWidget

logger = logging.getLogger(__name__)


class JournalForm(UDFFormMixin, BootstrapFormMixin, forms.ModelForm):
    """
    Form for creating/editing Journal header information.

    Fields:
        - journal_type: ForeignKey to JournalType
        - period: ForeignKey to AccountingPeriod
        - journal_date: Date of the entry
        - reference: Optional reference number
        - description: Optional description
        - currency_code: Currency code (e.g., USD)
        - exchange_rate: Exchange rate for multi-currency
        - status: Current status (draft, posted, approved)

    Validation:
        - journal_date must fall within an open accounting period
        - period must be open and current
        - currency_code must be active
    """

    class Meta:
        model = Journal
        fields = [
            'journal_type', 'period', 'journal_date', 'reference', 'description',
            'currency_code', 'exchange_rate', 'status'
        ]
        widgets = {
            'journal_type': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'aria-label': 'Journal Type'
            }),
            'period': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'aria-label': 'Accounting Period'
            }),
            'journal_date': DualCalendarWidget(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': 'required',
                'aria-label': 'Journal Date'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., INV-2025-001',
                'aria-label': 'Reference Number'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter journal description',
                'aria-label': 'Description'
            }),
            'currency_code': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'aria-label': 'Currency'
            }),
            'exchange_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'min': '0.000001',
                'value': '1.000000',
                'aria-label': 'Exchange Rate'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
                'required': 'required',
                'aria-label': 'Status'
            }),
        }

    def __init__(self, *args, **kwargs):
        """
        Initialize the form with organization context.

        Args:
            organization: Organization instance for filtering choices
            journal_type: Optional journal type to filter periods
        """
        self.organization = kwargs.pop('organization', None)
        self.journal_type = kwargs.pop('journal_type', None)

        super().__init__(*args, **kwargs)

        # Ensure journal_date is prefilling when no initial/data provided.
        if not self.data and not self.initial.get('journal_date'):
            today = timezone.localdate()
            self.initial['journal_date'] = today
            if 'journal_date' in self.fields:
                self.fields['journal_date'].initial = today

        calendar_mode = CalendarMode.normalize(
            getattr(self.organization, 'calendar_mode', CalendarMode.DEFAULT)
            if self.organization
            else CalendarMode.DEFAULT
        )
        base_attrs = self.fields['journal_date'].widget.attrs.copy()
        self.fields['journal_date'].widget = DualCalendarWidget(
            default_view=calendar_mode,
            attrs=base_attrs,
        )

        # Filter journal types by organization
        if self.organization:
            self.fields['journal_type'].queryset = JournalType.objects.filter(
                organization=self.organization
            )

            # Filter periods by organization and open status
            # AccountingPeriod now pins organization for direct filtering.
            periods_qs = AccountingPeriod.objects.filter(
                organization=self.organization,
                status='open'
            ).select_related('fiscal_year')

            if self.journal_type:
                # Could further filter by journal type if needed
                pass

            self.fields['period'].queryset = periods_qs

            # Filter currencies (should be organization-specific or global active)
            self.fields['currency_code'].queryset = Currency.objects.filter(
                is_active=True
            )
        else:
            # No organization - return empty querysets
            self.fields['journal_type'].queryset = JournalType.objects.none()
            self.fields['period'].queryset = AccountingPeriod.objects.none()
            self.fields['currency_code'].queryset = Currency.objects.none()

        # Set default exchange rate
        if not self.instance.pk:
            self.fields['exchange_rate'].initial = 1.0

    def clean_journal_date(self) -> Optional[str]:
        """
        Validate that journal date falls within an open accounting period.

        Raises:
            ValidationError: If date is not in an open period

        Returns:
            date: The cleaned journal_date
        """
        journal_date = self.cleaned_data.get('journal_date')

        if not journal_date or not self.organization:
            return journal_date

        # Check if date falls within an open accounting period
        if not AccountingPeriod.is_date_in_open_period(self.organization, journal_date):
            raise ValidationError(
                _('Journal date must fall within an open accounting period.'),
                code='date_not_in_period'
            )

        return journal_date

    def clean_period(self) -> Optional[AccountingPeriod]:
        """
        Validate that the selected period is open.

        Raises:
            ValidationError: If period is not open

        Returns:
            AccountingPeriod: The cleaned period
        """
        period = self.cleaned_data.get('period')

        if not period:
            return period

        if period.status != 'open':
            raise ValidationError(
                _('The selected accounting period is not open for posting.'),
                code='period_not_open'
            )

        return period

    def clean_currency_code(self) -> Optional[str]:
        """
        Validate that currency is active.

        Raises:
            ValidationError: If currency is inactive

        Returns:
            str: The cleaned currency_code
        """
        currency_value = self.cleaned_data.get('currency_code')

        if not currency_value:
            return currency_value

        if isinstance(currency_value, Currency):
            currency = currency_value
            currency_code = currency.currency_code
        else:
            currency_code = currency_value
            try:
                currency = Currency.objects.get(currency_code=currency_code)
            except Currency.DoesNotExist:
                raise ValidationError(
                    _('The selected currency does not exist.'),
                    code='currency_not_found'
                )

        if not currency.is_active:
            raise ValidationError(
                _('The selected currency is not active.'),
                code='currency_inactive'
            )

        return currency_code

    def clean_exchange_rate(self) -> Optional[float]:
        """
        Validate exchange rate is positive.

        Raises:
            ValidationError: If exchange rate is invalid

        Returns:
            float: The cleaned exchange_rate
        """
        exchange_rate = self.cleaned_data.get('exchange_rate')

        if exchange_rate is None:
            return exchange_rate

        if exchange_rate <= 0:
            raise ValidationError(
                _('Exchange rate must be greater than zero.'),
                code='invalid_exchange_rate'
            )

        return exchange_rate

    def clean(self) -> Dict:
        """
        Perform cross-field validation.

        Raises:
            ValidationError: If validation fails

        Returns:
            dict: The cleaned data
        """
        cleaned_data = super().clean()

        # If editing existing journal, validate it's not already posted
        if self.instance.pk and self.instance.status == 'posted':
            raise ValidationError(
                _('Cannot edit a posted journal entry.'),
                code='journal_posted'
            )

        # Validate journal_date and period consistency
        journal_date = cleaned_data.get('journal_date')
        period = cleaned_data.get('period')

        if journal_date and period:
            if not (period.start_date <= journal_date <= period.end_date):
                self.add_error('journal_date',
                    _('Journal date must be within the selected accounting period.')
                )

        return cleaned_data

    def save(self, commit: bool = True):
        instance = super().save(commit)
        if commit:
            self.save_udf_fields(instance)
        return instance

    def after_udf_save(self, instance, payload: Dict[str, Any]) -> None:
        prefixed_payload = self.udf_payload_with_form_names(payload)
        if not prefixed_payload:
            return
        current = instance.header_udf_data or {}
        merged = {**current, **prefixed_payload}
        if merged != current:
            instance.header_udf_data = merged
            instance.save(update_fields=["header_udf_data"])
