from django.utils.translation import gettext_lazy as _
from accounting.models import AccountingPeriod, Journal, JournalLine
from datetime import date

class JournalValidationService:
    """
    A service for validating journal entries.
    """
    def __init__(self, journal, form, formset, organization):
        self.journal = journal
        self.form = form
        self.formset = formset
        self.organization = organization
        self.errors = []

    def _validate_accounting_period(self, journal_date):
        """
        Validates that the journal date falls within an open accounting period.
        """
        if not isinstance(journal_date, date):
            self.errors.append(_("Invalid journal date format."))
            return

        period = AccountingPeriod.objects.filter(
            organization=self.organization,
            start_date__lte=journal_date,
            end_date__gte=journal_date,
            status='open'
        ).first()

        if not period:
            self.errors.append(_("Journal date must fall within an open accounting period."))

    def _validate_header(self):
        """
        Validates the main journal form (header).
        """
        if not self.form.is_valid():
            for field, errors in self.form.errors.items():
                for error in errors:
                    self.errors.append(f"{self.form.fields[field].label}: {error}")
            return False
        
        self._validate_accounting_period(self.form.cleaned_data.get('date'))
        return True

    def _validate_lines(self):
        """
        Validates the journal line formset.
        """
        if not self.formset.is_valid():
            for i, line_form in enumerate(self.formset):
                for field, errors in line_form.errors.items():
                    for error in errors:
                        self.errors.append(f"Line {i+1} - {line_form.fields[field].label}: {error}")
            return False

        total_debit = sum(line.cleaned_data.get('debit', 0) for line in self.formset if not line.cleaned_data.get('DELETE', False))
        total_credit = sum(line.cleaned_data.get('credit', 0) for line in self.formset if not line.cleaned_data.get('DELETE', False))

        if total_debit != total_credit:
            self.errors.append(_("Total debits must equal total credits."))
            return False
        
        return True

    def validate_all(self):
        """
        Runs all validations for the journal entry.
        """
        self.errors = [] # Clear previous errors
        header_valid = self._validate_header()
        lines_valid = self._validate_lines()

        return {
            'is_valid': not self.errors,
            'errors': self.errors
        }