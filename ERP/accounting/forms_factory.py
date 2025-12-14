from django import forms
from django.forms import modelform_factory, modelformset_factory

from utils.calendars import CalendarMode, get_calendar_mode
from utils.widgets import DualCalendarWidget
from .forms_mixin import BootstrapFormMixin
from .models import VoucherModeConfig
from .widgets import DatePicker, AccountChoiceWidget

# Minimal dynamic form builder for schema-driven forms

class FormBuilder:
    def __init__(self, schema, model=None, organization=None, user_perms=None, prefix=None,
                 phase=None, initial=None, disabled_fields=None, **kwargs):
        self.schema = schema
        self.model = model
        self.organization = organization
        self.user_perms = user_perms
        self.prefix = prefix
        self.phase = phase
        self.initial = initial
        # Default dynamic form 'currency' initial to organization's base currency
        try:
            if self.initial is None and self.organization is not None:
                base_cur = getattr(self.organization, 'base_currency_code_id', None) or getattr(self.organization, 'base_currency_code', None)
                if base_cur:
                    self.initial = {'currency': base_cur}
        except Exception:
            pass
        self.disabled_fields = disabled_fields or []
        self.kwargs = kwargs

    def _create_field_from_schema(self, config):
        """Create a form field from a schema definition."""
        field_type = config.get('type', 'char')
        field_class = self._map_type_to_field(field_type)
        
        field_kwargs = {
            'label': config.get('label'),
            'required': config.get('required', True),
            'help_text': config.get('help_text'),
            'min_length': config.get('min_length'),
            'max_length': config.get('max_length'),
        }

        # Handle kwargs for widget attributes
        widget_kwargs = config.get('kwargs', {})
        attrs = widget_kwargs.get('widget', {}).get('attrs', {})
        
        # Ensure 'form-control' class is always present for Bootstrap styling
        current_classes = attrs.get('class', '').split()
        if 'form-control' not in current_classes:
            current_classes.append('form-control')
        attrs['class'] = ' '.join(current_classes).strip()

        if field_type == 'date':
            attrs['type'] = 'date'  # Ensure date input type for date fields

        widget_class = self._map_type_to_widget(field_type)
        if widget_class:
            if widget_class is DualCalendarWidget:
                default_view = get_calendar_mode(
                    self.organization, default=CalendarMode.DEFAULT
                )
                field_kwargs['widget'] = widget_class(
                    default_view=default_view,
                    attrs=attrs,
                )
            else:
                field_kwargs['widget'] = widget_class(attrs=attrs)
        elif attrs:  # Fallback for fields without specific widget mapping but with attrs
            field_kwargs['widget'] = forms.TextInput(attrs=attrs)  # Default to TextInput if no specific widget

        if field_type == 'select':
            choices = config.get('choices', [])
            from django.apps import apps
            if isinstance(choices, str):
                # Treat as a model reference, use ModelChoiceField with queryset
                try:
                    model = apps.get_model('accounting', choices)
                    field_class = forms.ModelChoiceField
                    field_kwargs['queryset'] = model.objects.filter(is_active=True)
                    # Keep a simple to_field_name if present
                    field_kwargs['to_field_name'] = getattr(model._meta.pk, 'name', 'id')
                except LookupError:
                    # Fall back to an empty choice set
                    field_kwargs['choices'] = []
            else:
                # Ensure choices are in (value, label) format
                if choices and not isinstance(choices[0], (list, tuple)):
                    choices = [(c, c) for c in choices]
                field_kwargs['choices'] = choices
        elif field_type == 'account':
            # For ModelChoiceField, queryset is required. Assuming 'choices' in schema provides model name.
            from django.apps import apps
            model_name = config.get('choices')
            if model_name:
                try:
                    model = apps.get_model('accounting', model_name) # Assuming 'accounting' app
                    field_kwargs['queryset'] = model.objects.all()
                    field_kwargs['to_field_name'] = 'id' # Or 'code', 'name' depending on lookup
                except LookupError:
                    print(f"WARNING: Model {model_name} not found for account field.")
                    field_class = forms.CharField # Fallback to CharField if model not found
            else:
                field_class = forms.CharField # Fallback if no model name provided

        # Apply field-level schema flags (hidden/disabled/placeholder)
        if config.get('hidden'):
            from django.forms import widgets
            field_kwargs['widget'] = widgets.HiddenInput(attrs=attrs)
        if config.get('disabled'):
            field_kwargs['disabled'] = True
        placeholder = config.get('placeholder')
        if placeholder:
            attrs['placeholder'] = placeholder

        # Filter out None values
        field_kwargs = {k: v for k, v in field_kwargs.items() if v is not None}

        return field_class(**field_kwargs)

    def _map_type_to_field(self, field_type):
        """Map schema field type to a Django Form Field."""
        type_map = {
            'char': forms.CharField,
            'text': forms.CharField,
            'date': forms.DateField,
            'decimal': forms.DecimalField,
            'integer': forms.IntegerField,
            'boolean': forms.BooleanField,
            'select': forms.ChoiceField,
            'account': forms.ModelChoiceField,
        }
        return type_map.get(field_type, forms.CharField)

    def _map_type_to_widget(self, field_type):
        """Map schema field type to a Django Form Widget."""
        widget_map = {
            'text': forms.Textarea,
            'date': DualCalendarWidget,
            'account': AccountChoiceWidget,
            'select': forms.Select,
        }
        return widget_map.get(field_type)

    def build_form(self):
        """Dynamically build and return a Form class based on the schema."""
        form_fields = {}
        # Handle schema as a direct dictionary of fields or with a 'fields' key
        if isinstance(self.schema, dict):
            if 'fields' in self.schema and isinstance(self.schema['fields'], list):
                for field_config in self.schema['fields']:
                    field_name = field_config.get('name')
                    if field_name:
                        form_fields[field_name] = self._create_field_from_schema(field_config)
            else: # Assume schema is a direct dictionary of field_name: field_config
                for field_name, field_config in self.schema.items():
                    form_fields[field_name] = self._create_field_from_schema(field_config)

        # Create a dynamic form class
        BaseForm = type('DynamicBaseForm', (BootstrapFormMixin, forms.Form), form_fields)

        class DynamicForm(BaseForm):
            def __init__(self, *args, **kwargs):
                if self.form_builder.initial is not None:
                    kwargs.setdefault('initial', self.form_builder.initial)
                if self.form_builder.prefix is not None:
                    kwargs.setdefault('prefix', self.form_builder.prefix)
                
                super().__init__(*args, **kwargs)

                # Disable fields if needed
                for f_name in self.form_builder.disabled_fields:
                    if f_name in self.fields:
                        self.fields[f_name].disabled = True
            
            def save(self, commit=True):
                # This form is not a ModelForm, so we return cleaned_data
                # The view will handle saving the model instance
                return self.cleaned_data

        DynamicForm.form_builder = self
        return DynamicForm

    def build_formset(self, extra=1):
        """Dynamically build and return a FormSet class for line items."""
        LineForm = self.build_form()
        
        FormSet = forms.formset_factory(LineForm, extra=extra)

        class DynamicFormSet(FormSet):
            form_builder = self
            def __init__(self, *args, **kwargs):
                if self.form_builder.prefix is not None:
                    kwargs.setdefault('prefix', self.form_builder.prefix)
                
                # We don't use initial data for formsets in the same way
                # It's typically passed as `initial=[{...}, {...}]`
                super().__init__(*args, **kwargs)

                disabled_fields = getattr(self.form_builder, 'disabled_fields', None)
                if disabled_fields:
                    for form in self.forms:
                        for f_name in disabled_fields:
                            if f_name in form.fields:
                                form.fields[f_name].disabled = True
        
        return DynamicFormSet

def build_form(schema, **kwargs):
    """Build a single form."""
    return FormBuilder(schema, **kwargs).build_form()

def build_formset(schema, **kwargs):
    """Build a formset."""
    return FormBuilder(schema, **kwargs).build_formset()

from django.utils.functional import LazyObject

class LazyVoucherForms(LazyObject):
    def _setup(self):
        from .models import VoucherModeConfig
        self._wrapped = {
            config.code: FormBuilder(config.ui_schema).build_form()
            for config in VoucherModeConfig.objects.all()
        }

VOUCHER_FORMS = LazyVoucherForms()
