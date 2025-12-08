from django import forms
from accounting.models import CurrencyExchangeRate
from accounting.forms_mixin import BootstrapFormMixin


class CurrencyExchangeRateForm(BootstrapFormMixin, forms.ModelForm):
    """Form for creating and updating currency exchange rates."""

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        # When creating a new exchange rate, default the `from_currency` to
        # the organization's base currency but leave the `to_currency` empty
        # so users explicitly choose the target currency.
        if self.organization and not self.instance.pk:
            base_cur = getattr(self.organization, 'base_currency_code', None) or getattr(self.organization, 'base_currency_code_id', None)
            if base_cur and 'from_currency' in self.fields and not self.initial.get('from_currency'):
                self.initial['from_currency'] = base_cur
            if 'to_currency' in self.fields:
                # Clear default to encourage explicit selection
                self.initial['to_currency'] = None

    class Meta:
        model = CurrencyExchangeRate
        fields = [
            'from_currency',
            'to_currency',
            'rate_date',
            'exchange_rate',
            'is_average_rate',
            'source',
            'is_active',
        ]
        widgets = {
            'from_currency': forms.Select(attrs={'class': 'form-select'}),
            'to_currency': forms.Select(attrs={'class': 'form-select'}),
            'rate_date': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'is_average_rate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'source': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if self.organization and not self.instance.pk:
            from_currency = cleaned_data.get('from_currency')
            to_currency = cleaned_data.get('to_currency')
            rate_date = cleaned_data.get('rate_date')
            if from_currency and to_currency and rate_date:
                exists = CurrencyExchangeRate.objects.filter(
                    organization=self.organization,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate_date=rate_date,
                ).exists()
                if exists:
                    raise forms.ValidationError(
                        'An exchange rate for this currency pair and date already exists.'
                    )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance
