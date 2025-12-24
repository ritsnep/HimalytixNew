from decimal import Decimal

from django import forms

from utils.widgets import dual_date_widget

PAYMENT_METHOD_CHOICES = [
    ('cash', 'Cash'),
    ('bank', 'Bank'),
    ('bank_transfer', 'Bank Transfer'),
    ('cheque', 'Cheque'),
    ('wire_transfer', 'Wire Transfer'),
]

BANK_ACCOUNT_METHODS = {
    'bank',
    'bank_transfer',
    'cheque',
    'wire_transfer',
}


class PurchasePaymentForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    cash_bank_id = forms.ChoiceField(
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    due_date = forms.DateField(required=False)
    amount = forms.DecimalField(
        required=False,
        max_digits=19,
        decimal_places=4,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end'}),
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
    )
    DELETE = forms.BooleanField(required=False)

    def __init__(self, *args, invoice_date=None, cash_bank_choices=None, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invoice_date = invoice_date
        self.organization = organization
        self.fields['cash_bank_id'].choices = cash_bank_choices or [('', 'Select account')]
        self.fields['due_date'].widget = dual_date_widget(
            attrs={'class': 'form-control form-control-sm'},
            organization=organization,
            default_view='DUAL',
        )

    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('amount')
        if amount in (None, Decimal('0')):
            return cleaned
        if amount <= 0:
            self.add_error('amount', 'Amount must be positive.')
        method = cleaned.get('payment_method')
        if method in BANK_ACCOUNT_METHODS and not cleaned.get('cash_bank_id'):
            self.add_error('cash_bank_id', 'Please select a cash or bank account.')
        due_date = cleaned.get('due_date')
        if due_date and self.invoice_date and due_date < self.invoice_date:
            self.add_error('due_date', 'Payment due date cannot be before the invoice date.')
        return cleaned
