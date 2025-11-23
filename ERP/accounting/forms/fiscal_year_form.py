from django import forms
from accounting.models import FiscalYear
from accounting.forms_mixin import BootstrapFormMixin

class FiscalYearForm(BootstrapFormMixin, forms.ModelForm):
    code = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
        })
    )
    class Meta:
        model = FiscalYear
        fields = ('code', 'name', 'start_date', 'end_date', 'status', 'is_current','is_default')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'end_date': forms.TextInput(attrs={'class': 'form-control datepicker'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            from accounting.models import AutoIncrementCodeGenerator
            code_generator = AutoIncrementCodeGenerator(
                FiscalYear,
                'code',
                organization=self.organization,
                prefix='FY',
                suffix='',
            )
            generated_code = code_generator.generate_code()
            self.initial['code'] = generated_code
            self.fields['code'].initial = generated_code
