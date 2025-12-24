from django import forms
from accounting.models import Agent, AutoIncrementCodeGenerator
from accounting.forms_mixin import BootstrapFormMixin
from locations.models import LocationNode


class AgentForm(BootstrapFormMixin, forms.ModelForm):
    code = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
        })
    )

    class Meta:
        model = Agent
        fields = ('code', 'name', 'area', 'phone', 'email', 'commission_rate', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'commission_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.instance.organization = self.organization
        self.fields['area'].queryset = LocationNode.objects.filter(
            type=LocationNode.Type.AREA,
            is_active=True,
        )
        if not self.instance.pk and not self.initial.get('code'):
            code_generator = AutoIncrementCodeGenerator(
                Agent,
                'code',
                organization=self.organization,
                prefix='AGT',
                suffix='',
            )
            generated_code = code_generator.generate_code()
            self.initial['code'] = generated_code
            self.fields['code'].initial = generated_code

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization:
            instance.organization = self.organization
        if not instance.code:
            code_generator = AutoIncrementCodeGenerator(
                Agent,
                'code',
                organization=self.organization,
                prefix='AGT',
                suffix='',
            )
            instance.code = code_generator.generate_code()
        if commit:
            instance.save()
        return instance
