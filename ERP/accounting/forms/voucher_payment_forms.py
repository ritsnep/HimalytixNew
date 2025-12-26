from django import forms
from decimal import Decimal
from accounting.models import ChartOfAccount

class VoucherPaymentForm(forms.Form):
    payment_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    payment_method = forms.ChoiceField(choices=[('cash', 'Cash'), ('bank', 'Bank'), ('card', 'Card')], required=True)
    account = forms.ModelChoiceField(queryset=ChartOfAccount.objects.none(), required=True)
    amount = forms.DecimalField(required=True, min_value=Decimal('0.01'), max_digits=18, decimal_places=2)
    currency = forms.CharField(required=False, max_length=3)
    reference = forms.CharField(required=False, max_length=100)
    
    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = ChartOfAccount.objects.filter(organization=organization)
    
    def clean(self):
        cleaned = super().clean()
        currency = cleaned.get('currency')
        if currency and currency not in self.organization.active_currencies:
            raise forms.ValidationError({'currency': 'Invalid currency.'}, code='PAY-CURRENCY')
        return cleaned

VoucherPaymentFormSet = forms.formset_factory(VoucherPaymentForm, extra=1, can_delete=True)