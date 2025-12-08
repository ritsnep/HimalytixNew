"""
Base form mixin to apply Dason/Bootstrap widget classes.
"""
from django import forms

from accounting.models import Currency
from utils.widgets import dual_date_widget, set_default_date_initial

class BootstrapFormMixin(forms.Form):
    def __init__(self, *args, **kwargs):
        organization = kwargs.pop('organization', None)
        kwargs.pop('voucher_mode', None)
        ui_schema = kwargs.pop('ui_schema', None)
        if organization is not None and not getattr(self, "organization", None):
            self.organization = organization
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get('class', '')
            if 'form-control' not in css_class:
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
        self._apply_dual_calendar_widgets()
        # Apply schema-driven UI overrides (if provided). `ui_schema` may be
        # either a header-dict directly or full schema with 'header' key.
        if ui_schema:
            header = ui_schema.get('header') if isinstance(ui_schema, dict) and 'header' in ui_schema else ui_schema
            if isinstance(header, dict):
                self._apply_ui_schema(header)
        # Apply currency-specific defaults (querysets and initial values) after
        # widgets and other initialization have been applied. This centralizes
        # default-currency selection across forms and reduces duplication.
        self._apply_currency_defaults()

    def _apply_currency_defaults(self):
        """Set currency fields to the organization's base currency where
        applicable and filter currency querysets to active currencies.

        Fields considered: 'currency', 'default_currency', 'from_currency', 'to_currency'.
        """
        org = getattr(self, 'organization', None)
        if org:
            base_currency = getattr(org, 'base_currency_code', None)
        else:
            base_currency = None

        currency_model_qs = Currency.objects.filter(is_active=True)

        for name in ('currency', 'currency_code', 'txn_currency', 'default_currency', 'from_currency', 'to_currency'):
            if name in self.fields:
                field = self.fields[name]
                # If field is a ModelChoiceField and there's no queryset set,
                # set it to active currencies.
                try:
                    from django.forms import ModelChoiceField
                    if isinstance(field, ModelChoiceField):
                        # only set queryset if not set by form explicitly
                        if getattr(field, 'queryset', None) is None or field.queryset.model is None:
                            field.queryset = currency_model_qs
                except Exception:
                    # If imports or introspection fail, gracefully continue
                    pass
                # Set the initial value to base currency if no explicit initial is set
                if base_currency and (self.initial.get(name) is None) and (field.initial in (None, '')):
                    self.initial[name] = base_currency

    def _apply_ui_schema(self, header_schema: dict):
        """Apply a header schema (dict mapping field names to config) to an
        existing ModelForm instance. Supports the following schema attributes:
        - label: override field label
        - placeholder: set widget placeholder
        - hidden: mark as HiddenInput
        - disabled: set field.disabled
        - default: set initial/default value
        - choices: for select fields, set choices or queryset (supports model name)
        """
        from django.forms import widgets
        from django.apps import apps

        for field_name, config in (header_schema or {}).items():
            if field_name not in self.fields or not isinstance(config, dict):
                continue
            field = self.fields[field_name]
            # Override label
            if config.get('label'):
                field.label = config['label']
            # Placeholder
            if config.get('placeholder'):
                field.widget.attrs['placeholder'] = config['placeholder']
            # Hidden
            if config.get('hidden'):
                field.widget = widgets.HiddenInput(attrs=field.widget.attrs)
            # Disabled
            if config.get('disabled'):
                field.disabled = True
            # Default
            if config.get('default') not in (None, '') and not self.initial.get(field_name):
                self.initial[field_name] = config.get('default')
            # Choices or model-based choices
            choices = config.get('choices')
            if choices:
                if isinstance(choices, str):
                    try:
                        model = apps.get_model('accounting', choices)
                        # Only set queryset for ModelChoiceFields
                        from django.forms import ModelChoiceField
                        if isinstance(field, ModelChoiceField):
                            field.queryset = model.objects.filter(is_active=True)
                    except LookupError:
                        pass
                elif isinstance(choices, (list, tuple)):
                    # If it's a regular ChoiceField, set choices
                    try:
                        if hasattr(field, 'choices'):
                            field.choices = [(str(c), str(c)) if not isinstance(c, (list, tuple)) else c for c in choices]
                    except Exception:
                        pass

    def full_clean(self):
        """Run validation then tag invalid widgets for consistent styling."""
        super().full_clean()
        self._apply_error_classes()

    def _apply_dual_calendar_widgets(self):
        """Normalize all DateFields to the dual AD/BS widget."""
        organization = getattr(self, "organization", None)
        for name, field in self.fields.items():
            if isinstance(field, forms.DateField) and not field.widget.is_hidden:
                attrs = dict(getattr(field.widget, "attrs", {}) or {})
                field.widget = dual_date_widget(attrs=attrs, organization=organization)
                set_default_date_initial(self, name, field)

    def _apply_error_classes(self):
        """Ensure error fields render with Bootstrap's invalid state."""
        if not self.is_bound:
            return

        for name, field in self.fields.items():
            widget = field.widget
            classes = widget.attrs.get('class', '').split()
            if self.errors.get(name):
                if 'is-invalid' not in classes:
                    classes.append('is-invalid')
                widget.attrs['aria-invalid'] = 'true'
            else:
                classes = [cls for cls in classes if cls != 'is-invalid']
                widget.attrs.pop('aria-invalid', None)
            widget.attrs['class'] = ' '.join(classes).strip()
