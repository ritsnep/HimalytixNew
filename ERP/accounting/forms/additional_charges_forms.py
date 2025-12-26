from django import forms
from decimal import Decimal
from accounting.models import ChartOfAccount

class AdditionalChargeForm(forms.Form):
    description = forms.CharField(required=True, max_length=200)
    amount = forms.DecimalField(required=True, min_value=Decimal('0.01'), max_digits=18, decimal_places=2)
    gl_account = forms.CharField(required=True)  # Code or name
    
    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
    
    def clean_gl_account(self):
        account_str = self.cleaned_data['gl_account']
        # Resolve by code or name, scoped to org
        account = ChartOfAccount.objects.filter(
            organization=self.organization,
            account_code=account_str
        ).first() or ChartOfAccount.objects.filter(
            organization=self.organization,
            account_name__icontains=account_str
        ).first()
        if not account:
            raise forms.ValidationError('Invalid GL account.', code='VCH-CHG')
        return account.pk
    
    def clean(self):
        cleaned = super().clean()
        amount = cleaned.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError({'amount': 'Charge amount must be positive.'}, code='VCH-CHG')
        return cleaned

AdditionalChargeFormSet = forms.formset_factory(AdditionalChargeForm, extra=1, can_delete=True)