from django import forms
from django.forms import modelform_factory, modelformset_factory

from utils.calendars import CalendarMode, get_calendar_mode
from utils.widgets import DualCalendarWidget
from .forms_mixin import BootstrapFormMixin
from .models import VoucherConfiguration  # Updated import
from .widgets import DatePicker, AccountChoiceWidget

# Minimal dynamic form builder for schema-driven forms

class VoucherFormFactory:
    """
    Generic form factory for voucher configurations.
    Supports UDF injection and default value injection.
    """
    def __init__(self, configuration, model=None, organization=None, user_perms=None, prefix=None,
                 phase=None, initial=None, disabled_fields=None, **kwargs):
        self.configuration = configuration
        self.schema = configuration.ui_schema if hasattr(configuration, 'ui_schema') else configuration  # Handle both config object and direct schema
        self.model = model
        self.organization = organization
        self.user_perms = user_perms
        self.prefix = prefix
        self.phase = phase
        self.initial = initial or {}
        # Inject default values from configuration
        if hasattr(configuration, 'default_header') and configuration.default_header:
            self.initial.update(configuration.default_header)
        # Default dynamic form 'currency' initial to organization's base currency
        try:
            if not self.initial and self.organization is not None:
                base_cur = getattr(self.organization, 'base_currency_code_id', None) or getattr(self.organization, 'base_currency_code', None)
                if base_cur:
                    self.initial = {'currency': base_cur}
        except Exception:
            pass
        self.disabled_fields = disabled_fields or []
        self.kwargs = kwargs

    def _create_field_from_schema(self, config, field_name=None):
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
                    self.organization, default=CalendarMode.DUAL
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
                    queryset = model.objects.all()
                    # Only filter by is_active if the model has this field
                    if hasattr(model, 'is_active'):
                        queryset = queryset.filter(is_active=True)
                    field_kwargs['queryset'] = queryset
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

    def _maybe_build_fk_typeahead_fields(self, field_name, config):
        """Return (base_field, display_field) when field is an FK we want to render as typeahead."""
        if not self.model or not field_name:
            return None

        try:
            model_field = self.model._meta.get_field(field_name)
        except Exception:
            return None

        try:
            from django.db import models as dj_models
            if not isinstance(model_field, dj_models.ForeignKey):
                return None
        except Exception:
            return None

        related_model = model_field.remote_field.model
        related_name = getattr(related_model, '__name__', '')
        if related_name not in {
            'ChartOfAccount',
            'Vendor',
            'Customer',
            'Product',
            'CostCenter',
            'Department',
            'Project',
            'TaxCode',
        }:
            return None

        queryset = related_model.objects.all()
        if self.organization is not None and hasattr(related_model, 'organization'):
            queryset = queryset.filter(organization=self.organization)
        if hasattr(related_model, 'is_active'):
            try:
                queryset = queryset.filter(is_active=True)
            except Exception:
                pass

        base_label = config.get('label')
        required = config.get('required', True)

        # Hidden base field that actually binds to the model FK
        base_field = forms.ModelChoiceField(
            label=base_label,
            required=required,
            queryset=queryset,
            widget=forms.HiddenInput(),
        )

        # Visible display field used for typeahead
        endpoint_map = {
            # Use the exact COA search endpoint requested
            'ChartOfAccount': '/accounting/journal-entry/lookup/accounts/',
            'CostCenter': '/accounting/journal-entry/lookup/cost-centers/',
            'Department': '/accounting/journal-entry/lookup/departments/',
            'Project': '/accounting/journal-entry/lookup/projects/',
            'TaxCode': '/accounting/journal-entry/lookup/tax-codes/',
            'Vendor': '/accounting/journal-entry/lookup/vendors/',
            'Customer': '/accounting/journal-entry/lookup/customers/',
            'Product': '/accounting/journal-entry/lookup/products/',
        }
        display_attrs = {
            'class': 'form-control generic-typeahead',
            'autocomplete': 'off',
            'data-endpoint': endpoint_map.get(related_name, ''),
        }
        placeholder = config.get('placeholder')
        if placeholder:
            display_attrs['placeholder'] = placeholder
        if related_name == 'ChartOfAccount':
            display_attrs['class'] = 'form-control account-typeahead'

        display_field = forms.CharField(
            label=base_label,
            required=required,
            help_text=config.get('help_text'),
            widget=forms.TextInput(attrs=display_attrs),
        )

        return base_field, display_field

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
        """Dynamically build and return a Form class based on the configuration's ui_schema."""
        form_fields = {}
        schema = self.configuration.resolve_ui_schema() if hasattr(self.configuration, 'resolve_ui_schema') else self.schema

        # Support ui_schema that contains top-level 'header'/'lines' sections.
        # When building a header form, prefer the 'header' section if present.
        if isinstance(schema, dict) and ('header' in schema or 'lines' in schema):
            # Prefer header when available; fallback to lines only when header missing.
            header_section = schema.get('header')
            if header_section is not None:
                schema = header_section
            else:
                schema = schema.get('lines')

        model_field_names = set()
        if self.model:
            try:
                model_field_names = {f.name for f in self.model._meta.fields}
            except Exception:
                model_field_names = set()
        
        def _ordered_schema_items(schema_dict: dict):
            # Collect items and support explicit `__order__`, but allow
            # `order_no` (if present) to determine final ordering.
            explicit = schema_dict.get('__order__') if isinstance(schema_dict, dict) else None

            items = []
            for name, cfg in schema_dict.items():
                if name == '__order__':
                    continue
                items.append((name, cfg))

            # If explicit ordering is provided, respect it as the primary key
            if isinstance(explicit, list) and explicit:
                ordered = []
                seen = set()
                for name in explicit:
                    if name in schema_dict and name != '__order__':
                        ordered.append((name, schema_dict[name]))
                        seen.add(name)
                # Append any remaining items preserving dict insertion
                for name, cfg in items:
                    if name not in seen:
                        ordered.append((name, cfg))
                items = ordered

            # If any item has an explicit 'order_no', sort by it (stable)
            has_order_no = any(isinstance(cfg, dict) and 'order_no' in cfg for _, cfg in items)
            if has_order_no:
                try:
                    items = sorted(items, key=lambda nc: (nc[1].get('order_no') if isinstance(nc[1], dict) and nc[1].get('order_no') is not None else 9999))
                except Exception:
                    # Be conservative and fall back to original items order
                    pass

            for name, cfg in items:
                yield name, cfg

        # Handle schema as a list of field configs, a dict with 'fields' list,
        # or a direct dict of field_name: field_config
        if isinstance(schema, list):
            # Schema provided as ordered list -> preserve order, but prefer explicit 'order_no' if present
            list_items = list(schema)
            if any(isinstance(it, dict) and 'order_no' in it for it in list_items):
                try:
                    list_items = sorted(list_items, key=lambda it: it.get('order_no', 9999) if isinstance(it, dict) else 9999)
                except Exception:
                    pass
            for field_config in list_items:
                field_name = field_config.get('name')
                if not field_name:
                    continue
                fk_pair = self._maybe_build_fk_typeahead_fields(field_name, field_config)
                if fk_pair:
                    base_field, display_field = fk_pair
                    form_fields[field_name] = base_field
                    form_fields[f"{field_name}_display"] = display_field
                else:
                    form_fields[field_name] = self._create_field_from_schema(field_config, field_name=field_name)
        elif isinstance(schema, dict):
            if 'fields' in schema and isinstance(schema['fields'], list):
                field_list = list(schema['fields'])
                if any(isinstance(it, dict) and 'order_no' in it for it in field_list):
                    try:
                        field_list = sorted(field_list, key=lambda it: it.get('order_no', 9999) if isinstance(it, dict) else 9999)
                    except Exception:
                        pass
                for field_config in field_list:
                    field_name = field_config.get('name')
                    if field_name:
                        fk_pair = self._maybe_build_fk_typeahead_fields(field_name, field_config)
                        if fk_pair:
                            base_field, display_field = fk_pair
                            form_fields[field_name] = base_field
                            form_fields[f"{field_name}_display"] = display_field
                        else:
                            form_fields[field_name] = self._create_field_from_schema(field_config, field_name=field_name)
            else:  # Assume schema is a direct dictionary of field_name: field_config
                for field_name, field_config in _ordered_schema_items(schema):
                    fk_pair = self._maybe_build_fk_typeahead_fields(field_name, field_config)
                    if fk_pair:
                        base_field, display_field = fk_pair
                        form_fields[field_name] = base_field
                        form_fields[f"{field_name}_display"] = display_field
                    else:
                        form_fields[field_name] = self._create_field_from_schema(field_config, field_name=field_name)

        # Create a dynamic form class - ModelForm if model is provided, otherwise regular Form
        if self.model:
            # Create ModelForm
            meta_fields = [name for name in form_fields.keys() if name in model_field_names]
            Meta = type('Meta', (), {'model': self.model, 'fields': meta_fields})
            form_fields['Meta'] = Meta
            BaseForm = type('DynamicModelForm', (BootstrapFormMixin, forms.ModelForm), form_fields)
        else:
            # Create regular Form
            BaseForm = type('DynamicBaseForm', (BootstrapFormMixin, forms.Form), form_fields)

        class DynamicForm(BaseForm):
            def __init__(self, *args, **kwargs):
                if self.form_factory.initial is not None:
                    kwargs.setdefault('initial', self.form_factory.initial)
                if self.form_factory.prefix is not None:
                    kwargs.setdefault('prefix', self.form_factory.prefix)
                
                super().__init__(*args, **kwargs)

                # Populate *_display fields from instance when possible
                try:
                    if getattr(self, 'instance', None) is not None:
                        for name in list(self.fields.keys()):
                            if not name.endswith('_display'):
                                continue
                            base_name = name[:-8]
                            if hasattr(self.instance, base_name):
                                val = getattr(self.instance, base_name)
                                if val:
                                    self.initial.setdefault(name, str(val))
                except Exception:
                    pass

                # Disable fields if needed
                for f_name in self.form_factory.disabled_fields:
                    if f_name in self.fields:
                        self.fields[f_name].disabled = True
            
            def save(self, commit=True):
                if self.form_factory.model:
                    # This is a ModelForm, save normally
                    instance = super().save(commit=commit)

                    # Persist extra schema fields into udf_data if available
                    try:
                        if hasattr(instance, 'udf_data') and isinstance(instance.udf_data, dict):
                            extra = {
                                k: self.cleaned_data.get(k)
                                for k in self.cleaned_data.keys()
                                if k not in model_field_names and not k.endswith('_display')
                            }
                            if extra:
                                instance.udf_data.update(extra)
                                if commit:
                                    instance.save(update_fields=['udf_data'])
                    except Exception:
                        pass

                    return instance
                else:
                    # This form is not a ModelForm, so we return cleaned_data
                    # The view will handle saving the model instance
                    return self.cleaned_data

        DynamicForm.form_factory = self
        return DynamicForm

    def build_formset(self, extra=1):
        """Dynamically build and return a FormSet class for line items."""
        # For formsets, prefer building the form using the 'lines' schema
        # If this factory was constructed with a VoucherConfiguration (self.schema is the UI dict),
        # we must avoid build_form() picking the header section. Build a temporary factory using
        # only the 'lines' schema so the line form fields are correct.
        LineForm = None
        if isinstance(self.schema, dict) and 'lines' in self.schema:
            lines_schema = self.schema.get('lines') or {}
            temp_factory = VoucherFormFactory(
                lines_schema,
                model=self.model,
                organization=self.organization,
                prefix=self.prefix,
                disabled_fields=self.disabled_fields,
            )
            LineForm = temp_factory.build_form()

        # Fallback: build a regular form (will pick top-level schema/ header if lines missing)
        if LineForm is None:
            LineForm = self.build_form()
        
        FormSet = forms.formset_factory(LineForm, extra=extra)

        class DynamicFormSet(FormSet):
            form_factory = self
            def __init__(self, *args, **kwargs):
                if self.form_factory.prefix is not None:
                    kwargs.setdefault('prefix', self.form_factory.prefix)
                
                # We don't use initial data for formsets in the same way
                # It's typically passed as `initial=[{...}, {...}]`
                super().__init__(*args, **kwargs)

                disabled_fields = getattr(self.form_factory, 'disabled_fields', None)
                if disabled_fields:
                    for form in self.forms:
                        for f_name in disabled_fields:
                            if f_name in form.fields:
                                form.fields[f_name].disabled = True
        
        return DynamicFormSet

    @staticmethod
    def get_generic_voucher_form(voucher_config, organization, instance=None, data=None, files=None, **kwargs):
        """
        Create a generic voucher header form.
        """
        form_kwargs = {
            'configuration': voucher_config,
            'organization': organization,
            **kwargs
        }
        
        if instance:
            form_kwargs['instance'] = instance
        if data is not None:
            form_kwargs['data'] = data
        if files is not None:
            form_kwargs['files'] = files
        # Provide the header model so FK fields (vendor, etc) are detected properly.
        # The authoritative mapping lives in `accounting.forms.form_factory`.
        try:
            from accounting.forms.form_factory import VoucherFormFactory as FormsFactoryLegacy
            header_model = FormsFactoryLegacy._get_model_for_voucher_config(voucher_config)
            form_kwargs['model'] = header_model
        except Exception:
            pass

        factory = VoucherFormFactory(**form_kwargs)
        return factory.build_form()

    @staticmethod
    def get_generic_voucher_formset(voucher_config, organization, instance=None, data=None, files=None, **kwargs):
        """
        Create a generic voucher line formset.
        """
        form_kwargs = {
            'configuration': voucher_config,
            'organization': organization,
            **kwargs
        }

        # Provide the line model to the factory so line-specific fields (FKs/typeaheads)
        # can be constructed correctly when building the line forms.
        try:
            from accounting.forms.form_factory import VoucherFormFactory as FormsFactoryLegacy
            line_model = FormsFactoryLegacy._get_line_model_for_voucher_config(voucher_config)
            form_kwargs['model'] = line_model
        except Exception:
            pass
        
        if data is not None:
            form_kwargs['data'] = data
        if files is not None:
            form_kwargs['files'] = files
        
        factory = VoucherFormFactory(**form_kwargs)
        return factory.build_formset()

def build_form(schema, **kwargs):
    """Build a single form."""
    return VoucherFormFactory(schema, **kwargs).build_form()

def build_formset(schema, **kwargs):
    """Build a formset."""
    return VoucherFormFactory(schema, **kwargs).build_formset()

from django.utils.functional import LazyObject

# Backward-compatible alias
FormBuilder = VoucherFormFactory

class LazyVoucherForms(LazyObject):
    def _setup(self):
        from .models import VoucherModeConfig
        self._wrapped = {
            config.code: FormBuilder(config.ui_schema).build_form()
            for config in VoucherModeConfig.objects.all()
        }

VOUCHER_FORMS = LazyVoucherForms()

def build_form(schema, **kwargs):
    """Build a single form."""
    return VoucherFormFactory(schema, **kwargs).build_form()

def build_formset(schema, **kwargs):
    """Build a formset."""
    return VoucherFormFactory(schema, **kwargs).build_formset()
