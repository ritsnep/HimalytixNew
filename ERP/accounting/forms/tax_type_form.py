from django import forms
from accounting.models import TaxType, TaxAuthority
from accounting.forms_mixin import BootstrapFormMixin


class TaxTypeForm(BootstrapFormMixin, forms.ModelForm):
    """Form for creating and updating :class:`TaxType` records."""

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields['authority'].queryset = TaxAuthority.objects.filter(organization=self.organization)

    class Meta:
        model = TaxType
        fields = [
            'code',
            'name',
            'authority',
            'filing_frequency',
            'is_active',
            'description',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'authority': forms.Select(attrs={'class': 'form-select'}),
            'filing_frequency': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }