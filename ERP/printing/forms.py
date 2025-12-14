from django import forms
from django.core.exceptions import ValidationError

from .models import PrintTemplate
from .utils import TEMPLATE_CHOICES, PAPER_SIZES, DEFAULT_TOGGLES


class PrintTemplateForm(forms.ModelForm):
    """Form for creating/editing print templates."""

    class Meta:
        model = PrintTemplate
        fields = ['document_type', 'name', 'paper_size', 'config']
        widgets = {
            'config': forms.HiddenInput(),  # We'll handle this with JS
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.organization = kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)

        # Set choices for document_type
        self.fields['document_type'].choices = PrintTemplate.DOCUMENT_TYPES

        # Set choices for paper_size
        self.fields['paper_size'].choices = PAPER_SIZES

        # Initialize config with defaults if creating
        if not self.instance.pk:
            self.initial_config = DEFAULT_TOGGLES.copy()
            self.initial_config.update({
                'template_name': 'classic',
                'paper_size': 'A4',
            })
        else:
            self.initial_config = self.instance.config.copy()

    def clean_name(self):
        name = self.cleaned_data['name']
        document_type = self.cleaned_data.get('document_type')
        if document_type:
            # Check uniqueness
            qs = PrintTemplate.objects.filter(
                user=self.user,
                organization=self.organization,
                document_type=document_type,
                name=name
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("A template with this name already exists for this document type.")
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        instance.organization = self.organization
        if commit:
            instance.save()
        return instance