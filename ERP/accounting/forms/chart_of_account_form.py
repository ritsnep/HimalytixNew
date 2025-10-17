from django import forms
from accounting.models import ChartOfAccount
from accounting.forms_mixin import BootstrapFormMixin

class ChartOfAccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ChartOfAccount
        fields = '__all__'
        widgets = {
            'account_code': forms.TextInput(attrs={'class': 'form-control'}),
            'account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_account': forms.Select(attrs={'class': 'form-select'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'currency_code': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Custom logic for ChartOfAccountForm can go here
