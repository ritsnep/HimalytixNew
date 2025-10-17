from django import forms
from django.core.validators import RegexValidator
from accounting.models import Currency
from accounting.forms_mixin import BootstrapFormMixin


class CurrencyForm(BootstrapFormMixin, forms.ModelForm):
    """Form for creating and updating currencies."""

    currency_code = forms.CharField(
        max_length=3,
        validators=[RegexValidator(r'^[A-Z]{3}$', 'Enter a 3-letter currency code.')],
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Currency
        fields = ['currency_code', 'currency_name', 'symbol', 'is_active']
        widgets = {
            'currency_name': forms.TextInput(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }