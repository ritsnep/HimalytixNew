import json
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import AccountingPeriod, ChartOfAccount
from accounting.config.settings import journal_entry_settings
 
class JournalValidationService:
    """
    A centralized service for validating journal entries.
    """

    def __init__(self, organization):
        self.organization = organization

    def validate_journal_entry(self, journal_data, lines_data):
        """
        Performs comprehensive validation for a journal entry.
        Returns a dictionary of errors.
        """
        errors = {
            'header': {},
            'lines': [],
            'general': []
        }

        # Rule: Check for balanced debits and credits
        total_debit = sum(Decimal(line.get('debit_amount', 0) or 0) for line in lines_data)
        total_credit = sum(Decimal(line.get('credit_amount', 0) or 0) for line in lines_data)
        if total_debit != total_credit:
            errors['general'].append(_('Total Debit must equal Total Credit.'))

        # Rule: Posting date must be in an open period
        journal_date = journal_data.get('journal_date')
        if journal_date and journal_entry_settings.enforce_fiscal_year:
            if not AccountingPeriod.is_date_in_open_period(self.organization, journal_date):
                errors['header']['journal_date'] = _('The posting date is not in an open accounting period.')

        # Rule: Prevent duplicate line numbers and missing fields
        line_numbers = set()
        for i, line in enumerate(lines_data):
            line_errors = {}
            line_number = line.get('line_number')
            if not line_number:
                line_errors['line_number'] = _('Line number is required.')
            elif line_number in line_numbers:
                line_errors['line_number'] = _('Duplicate line number.')
            else:
                line_numbers.add(line_number)

            if not line.get('account'):
                line_errors['account'] = _('Account is required.')

            if not line.get('debit_amount') and not line.get('credit_amount'):
                line_errors['amount'] = _('Either debit or credit amount is required.')

            if line_errors:
                errors['lines'].append({'index': i, 'errors': line_errors})

        # Config-driven validation rules

        # Filter out empty error categories
        errors = {k: v for k, v in errors.items() if v}
        return errors