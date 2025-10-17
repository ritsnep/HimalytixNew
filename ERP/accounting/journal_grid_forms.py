# accounting/journal_grid_forms.py
"""
This module contains the forms for the journal entry grid.
"""
from decimal import Decimal, InvalidOperation
from typing import Optional
from django import forms
from .models import Journal, JournalLine, ChartOfAccount, Department, Project, CostCenter, Currency

class JournalGridLineForm(forms.ModelForm):
    """
    A form for a single line in the journal entry grid.
    """
    debit_amount = forms.CharField(required=False)
    credit_amount = forms.CharField(required=False)

    class Meta:
        model = JournalLine
        fields = ['account', 'description', 'debit_amount', 'credit_amount',
                  'department', 'project', 'cost_center', 'txn_currency',
                  'fx_rate']
        widgets = {
            'account': forms.TextInput(attrs={'class': 'form-control je-cell je-account', 'autocomplete': 'off'}),
            'description': forms.TextInput(attrs={'class': 'form-control je-cell'}),
            'department': forms.TextInput(attrs={'class': 'form-control je-cell', 'autocomplete': 'off'}),
            'project': forms.TextInput(attrs={'class': 'form-control je-cell', 'autocomplete': 'off'}),
            'cost_center': forms.TextInput(attrs={'class': 'form-control je-cell', 'autocomplete': 'off'}),
            'txn_currency': forms.TextInput(attrs={'class': 'form-control je-cell'}),
            'fx_rate': forms.TextInput(attrs={'class': 'form-control je-cell'}),
        }

    def __init__(self, *args, organization: Optional[object] = None, **kwargs):
        super().__init__(*args, **kwargs)
        # supply organization‑filtered querysets if needed
        self.organization = organization

    def _to_decimal(self, value: str) -> Decimal:
        """
        Converts a string to a Decimal, handling common number formats.
        """
        if not value:
            return Decimal('0')
        s = str(value).strip()
        # normalise common number formats, treat last separator as decimal
        if ',' in s and '.' in s:
            last = max(s.rfind(','), s.rfind('.'))
            int_part = s[:last].replace(',', '').replace('.', '')
            dec_part = s[last+1:]
            s = f"{int_part}.{dec_part}"
        else:
            s = s.replace(',', '.')
        try:
            return Decimal(s)
        except InvalidOperation:
            raise forms.ValidationError("Invalid number")

    def clean(self):
        cleaned = super().clean()
        debit_raw = cleaned.get('debit_amount')
        credit_raw = cleaned.get('credit_amount')
        debit = self._to_decimal(debit_raw)
        credit = self._to_decimal(credit_raw)
        cleaned['debit_amount'] = debit
        cleaned['credit_amount'] = credit
        if debit > 0 and credit > 0:
            raise forms.ValidationError("Only one of Debit or Credit can be > 0 on a row.")
        if debit == 0 and credit == 0:
            # allow blank row; it will be ignored when saving
            pass
        account = cleaned.get('account')
        if not account and (debit > 0 or credit > 0 or cleaned.get('description')):
            raise forms.ValidationError("Account is required for non‑blank lines.")
        return cleaned

JournalGridLineFormSet = forms.formset_factory(
    JournalGridLineForm,
    extra=0,
    can_delete=True,
)
