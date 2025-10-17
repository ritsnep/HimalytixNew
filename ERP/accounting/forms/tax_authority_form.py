from django import forms
from accounting.models import TaxAuthority
from accounting.forms_mixin import BootstrapFormMixin


class TaxAuthorityForm(BootstrapFormMixin, forms.ModelForm):
    """Form for creating and updating :class:`TaxAuthority` records."""

    class Meta:
        model = TaxAuthority
        fields = [
            'code',
            'name',
            'country_code',
            'description',
            'is_active',
            'is_default',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'country_code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
