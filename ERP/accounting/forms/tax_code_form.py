from django import forms
from accounting.models import TaxCode, TaxType, TaxAuthority

try:
    from accounting.forms_mixin import BootstrapFormMixin
except ImportError:
    class BootstrapFormMixin:
        pass

class TaxCodeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaxCode
        fields = [
            'code', 'name', 'tax_type', 'tax_authority', 'tax_rate', 'rate',
            'description', 'is_active', 'is_recoverable', 'is_compound',
            'effective_from', 'effective_to', 'sales_account', 'purchase_account',
            'report_line_code',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_type': forms.Select(attrs={'class': 'form-select'}),
            'tax_authority': forms.Select(attrs={'class': 'form-select'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_recoverable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_compound': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'effective_from': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'effective_to': forms.DateInput(attrs={'class': 'form-control datepicker'}),
            'sales_account': forms.Select(attrs={'class': 'form-select'}),
            'purchase_account': forms.Select(attrs={'class': 'form-select'}),
            'report_line_code': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['tax_type'].queryset = TaxType.objects.filter(organization=self.organization)
            self.fields['tax_authority'].queryset = TaxAuthority.objects.filter(organization=self.organization)
            if 'sales_account' in self.fields:
                self.fields['sales_account'].queryset = self.fields['sales_account'].queryset.filter(organization=self.organization)
            if 'purchase_account' in self.fields:
                self.fields['purchase_account'].queryset = self.fields['purchase_account'].queryset.filter(organization=self.organization)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance 