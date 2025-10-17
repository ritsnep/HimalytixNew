from django import forms
from ..models import GeneralLedger, ChartOfAccount, Journal, JournalLine, AccountingPeriod, Department, Project, CostCenter
from ..forms_mixin import BootstrapFormMixin

class GeneralLedgerForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = GeneralLedger
        fields = [
            'account', 'journal', 'journal_line', 'period', 'transaction_date',
            'debit_amount', 'credit_amount', 'description', 'department',
            'project', 'cost_center'
        ]
        widgets = {
            'account': forms.Select(attrs={'class': 'form-select'}),
            'journal': forms.Select(attrs={'class': 'form-select'}),
            'journal_line': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'transaction_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'debit_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'credit_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'cost_center': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if organization:
            self.fields['account'].queryset = ChartOfAccount.objects.filter(organization=organization)
            self.fields['journal'].queryset = Journal.objects.filter(organization=organization)
            self.fields['journal_line'].queryset = JournalLine.objects.filter(journal__organization=organization)
            self.fields['period'].queryset = AccountingPeriod.objects.filter(fiscal_year__organization=organization)
            self.fields['department'].queryset = Department.objects.filter(organization=organization)
            self.fields['project'].queryset = Project.objects.filter(organization=organization)
            self.fields['cost_center'].queryset = CostCenter.objects.filter(organization=organization)

    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get('debit_amount')
        credit = cleaned_data.get('credit_amount')

        debit = debit if debit is not None else 0
        credit = credit if credit is not None else 0

        if (debit == 0 and credit == 0) or (debit > 0 and credit > 0):
            raise forms.ValidationError(
                "A general ledger entry must have either a Debit amount or a Credit amount, but not both, and not neither."
            )
        return cleaned_data