from django import forms
from accounting.models import VoucherModeConfig, Currency, JournalType
from accounting.forms_mixin import BootstrapFormMixin
import json

class VoucherModeConfigForm(BootstrapFormMixin, forms.ModelForm):
    ui_schema = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10})
    )
    class Meta:
        model = VoucherModeConfig
        fields = (
            'name', 'description', 'journal_type', 'is_default',
            'layout_style', 'show_account_balances', 'show_tax_details',
            'show_dimensions', 'allow_multiple_currencies',
            'require_line_description', 'default_currency', 'ui_schema'
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'journal_type': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
    def clean_ui_schema(self):
        data = self.cleaned_data.get('ui_schema')
        if not data:
            return {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON: {exc}")
        if not isinstance(data, dict):
            raise forms.ValidationError("UI schema must be a JSON object.")
        return data
