from django import forms
from accounting.models import VoucherModeConfig, Currency, JournalType
from accounting.forms_mixin import BootstrapFormMixin

class VoucherModeConfigForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VoucherModeConfig
        fields = (
            'code', 'name', 'description', 'module', 'journal_type', 'is_default',
            'affects_gl', 'affects_inventory', 'requires_approval',
            'layout_style', 'show_account_balances', 'show_tax_details',
            'show_dimensions', 'allow_multiple_currencies',
            'require_line_description', 'default_currency'
        )
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'module': forms.Select(attrs={'class': 'form-select'}),
            'journal_type': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'affects_gl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'affects_inventory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'layout_style': forms.Select(attrs={'class': 'form-select'}),
            'show_account_balances': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_tax_details': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_dimensions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_multiple_currencies': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_line_description': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_currency': forms.Select(attrs={'class': 'form-select'}),
        }
    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        currency_choices = [(currency.currency_code, f"{currency.currency_code} - {currency.currency_name}") 
                           for currency in Currency.objects.filter(is_active=True)]
        self.fields['default_currency'].choices = currency_choices
        if self.organization:
            self.fields['journal_type'].queryset = JournalType.objects.filter(
                organization=self.organization,
                is_active=True
            )
    def clean_code(self):
        code = self.cleaned_data.get('code') or ''
        return code.strip()
