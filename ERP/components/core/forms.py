from typing import Any, Dict, List, Optional, Type, Union

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import ModelForm
from django.forms.widgets import Media


class DynamicFormMixin:
    """
    Mixin that adds dynamic field configuration capabilities to forms.
    """
    def __init__(self, *args, **kwargs):
        self.field_config = kwargs.pop('field_config', {})
        schema_fields = kwargs.pop('schema_fields', None)
        super().__init__(*args, **kwargs)
        if schema_fields:
            self.add_fields_from_schema(schema_fields)
        self.configure_fields()

    def configure_fields(self):
        """Configure form fields based on field_config."""
        for field_name, config in self.field_config.items():
            if field_name in self.fields:
                field = self.fields[field_name]
                
                # Apply enabled/disabled state
                if 'enabled' in config:
                    field.disabled = not config['enabled']
                
                # Apply custom validation
                if 'validators' in config:
                    field.validators.extend(config['validators'])
                
                # Apply widget attributes
                if 'widget_attrs' in config:
                    field.widget.attrs.update(config['widget_attrs'])
                    
                # Apply custom CSS classes
                if 'css_classes' in config:
                    classes = field.widget.attrs.get('class', '').split()
                    classes.extend(config['css_classes'])
                    field.widget.attrs['class'] = ' '.join(classes)

    def add_field(self, name: str, field: forms.Field, config: Optional[Dict] = None):
        """Dynamically add a new field to the form."""
        self.fields[name] = field
        if config:
            self.field_config[name] = config
            self.configure_fields()

    def remove_field(self, name: str):
        """Remove a field from the form."""
        if name in self.fields:
            del self.fields[name]
            if name in self.field_config:
                del self.field_config[name]

    def get_layout(self) -> List[Dict]:
        """Get the form layout configuration."""
        return getattr(self, 'layout', [])

    def add_fields_from_schema(self, schema_fields):
        """
        Add fields to the form based on schema metadata.
        """
        from django import forms
        for f in schema_fields:
            field_type = f['DataType']
            name = f['FieldName']
            label = f.get('DisplayName', name)
            required = f.get('IsRequired', False)
            help_text = f.get('HelpText', '')
            initial = f.get('DefaultValue', None)
            widget_attrs = {'placeholder': f.get('Placeholder', '')}
            if field_type in ('varchar', 'text'):
                field = forms.CharField(label=label, required=required, help_text=help_text, initial=initial, widget=forms.TextInput(attrs=widget_attrs))
            elif field_type in ('int', 'bigint'):
                field = forms.IntegerField(label=label, required=required, help_text=help_text, initial=initial, widget=forms.NumberInput(attrs=widget_attrs))
            elif field_type in ('decimal', 'float'):
                field = forms.FloatField(label=label, required=required, help_text=help_text, initial=initial, widget=forms.NumberInput(attrs=widget_attrs))
            elif field_type == 'date':
                field = forms.DateField(label=label, required=required, help_text=help_text, initial=initial, widget=forms.DateInput(attrs=widget_attrs))
            elif field_type == 'boolean':
                field = forms.BooleanField(label=label, required=required, help_text=help_text, initial=initial)
            elif field_type == 'select':
                field = forms.ChoiceField(label=label, required=required, help_text=help_text, choices=f.get('Options', []), initial=initial)
            else:
                field = forms.CharField(label=label, required=required, help_text=help_text, initial=initial, widget=forms.TextInput(attrs=widget_attrs))
            self.add_field(name, field, config={
                'enabled': f.get('IsActive', True),
                'widget_attrs': widget_attrs,
                'css_classes': ['udf-field'],
            })


class DynamicForm(DynamicFormMixin, forms.Form):
    """Base form class with dynamic field configuration."""
    pass


class DynamicModelForm(DynamicFormMixin, ModelForm):
    """Model form with dynamic field configuration."""
    pass


class FormFieldConfigBuilder:
    """Helper class to build field configurations."""
    def __init__(self):
        self.config = {}

    def set_enabled(self, enabled: bool = True):
        self.config['enabled'] = enabled
        return self

    def add_validator(self, validator_func):
        if 'validators' not in self.config:
            self.config['validators'] = []
        self.config['validators'].append(validator_func)
        return self

    def set_widget_attrs(self, attrs: Dict):
        if 'widget_attrs' not in self.config:
            self.config['widget_attrs'] = {}
        self.config['widget_attrs'].update(attrs)
        return self

    def add_css_classes(self, *classes):
        if 'css_classes' not in self.config:
            self.config['css_classes'] = []
        self.config['css_classes'].extend(classes)
        return self

    def build(self) -> Dict:
        return self.config
