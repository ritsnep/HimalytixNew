from decimal import Decimal

from django import forms
from django.utils import timezone

from accounting.forms_mixin import BootstrapFormMixin
from accounting.models import (
    ExpenseCategory,
    ExpenseEntry,
    JournalType,
    ChartOfAccount,
)
from accounting.services.expense_service import ExpenseEntryService


class ExpenseEntryForm(BootstrapFormMixin, forms.ModelForm):
    receipt = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='Optional receipt image for audit trail.',
    )

    class Meta:
        model = ExpenseEntry
        fields = [
            'category',
            'entry_date',
            'amount',
            'description',
            'reference',
            'journal_type',
            'payment_account',
            'paid_via',
            'gst_applicable',
            'gst_amount',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'entry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'journal_type': forms.Select(attrs={'class': 'form-select'}),
            'payment_account': forms.Select(attrs={'class': 'form-select'}),
            'paid_via': forms.Select(attrs={'class': 'form-select'}),
            'gst_applicable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gst_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        help_texts = {
            'paid_via': 'Choose the account that funded the expense or the payable account if unpaid.',
            'gst_applicable': 'Mark if GST/VAT was charged on this expense.',
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['category'].queryset = ExpenseCategory.objects.filter(
                organization=self.organization, is_active=True
            )
            self.fields['payment_account'].queryset = ChartOfAccount.objects.filter(
                organization=self.organization, is_active=True
            )
            self.fields['journal_type'].queryset = JournalType.objects.filter(
                organization=self.organization, is_active=True
            )
        else:
            self.fields['category'].queryset = ExpenseCategory.objects.none()
            self.fields['payment_account'].queryset = ChartOfAccount.objects.none()
            self.fields['journal_type'].queryset = JournalType.objects.none()
        self.fields['entry_date'].initial = timezone.now().date()

    def clean_gst_amount(self):
        gst_amount = self.cleaned_data.get('gst_amount') or Decimal('0')
        if gst_amount < 0:
            raise forms.ValidationError('GST amount cannot be negative.')
        return gst_amount

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('amount')
        gst_amount = cleaned.get('gst_amount') or Decimal('0')
        if amount and gst_amount and gst_amount > amount:
            raise forms.ValidationError('GST amount cannot exceed the total amount.')
        if not cleaned.get('payment_account'):
            raise forms.ValidationError('A payment account is required to credit the ledger.')
        return cleaned

    def create_expense_entry(self, user):
        if not self.organization:
            raise forms.ValidationError('Organization context is required to record an expense.')
        data = self.cleaned_data
        attachments = [data.get('receipt')] if data.get('receipt') else None
        service = ExpenseEntryService(user, self.organization)
        return service.create_expense_entry(
            category=data['category'],
            entry_date=data['entry_date'],
            amount=data['amount'],
            description=data.get('description'),
            reference=data.get('reference'),
            journal_type=data.get('journal_type'),
            payment_account=data['payment_account'],
            paid_via=data['paid_via'],
            gst_applicable=data.get('gst_applicable', False),
            gst_amount=data.get('gst_amount') or Decimal('0'),
            attachments=attachments,
        )
