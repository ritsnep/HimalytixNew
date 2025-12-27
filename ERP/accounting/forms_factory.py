import logging
from django import forms
import copy
from django.forms import modelform_factory, modelformset_factory

from utils.calendars import CalendarMode, get_calendar_mode
from utils.widgets import DualCalendarWidget
from .forms_mixin import BootstrapFormMixin
from .widgets import DatePicker, AccountChoiceWidget, TypeaheadInput
from .forms.journal_form import JournalForm
from .forms.journal_line_form import JournalLineForm, JournalLineFormSet
from .models import Journal, JournalLine
from accounting.schema_validation import validate_ui_schema
from accounting.services.voucher_errors import VoucherProcessError

logger = logging.getLogger(__name__)


def configure_widget_for_schema(field_name, field_schema, widget):
    """
    Inject HTML data attributes for dynamic UI behavior (typeahead, date, etc.).
    Uses TypeaheadInput for lookup fields to ensure data-* attributes persist.
    """
    field_type = (field_schema or {}).get('type') or (field_schema or {}).get('field_type')
    logger.debug(f"configure_widget_for_schema: field_name={field_name}, field_type={field_type}, widget_class={widget.__class__.__name__}")
    lookup_aliases = {
        'account': 'account',
        'party': 'party',
        'customer': 'customer',
        'vendor': 'vendor',
        'agent': 'agent',
        'product': 'product',
        'warehouse': 'warehouse',
        'cost_center': 'cost_center',
        'department': 'department',
        'project': 'project',
        'journal_type': 'journal_type',
        'period': 'period',
        'currency': 'currency',
        'rate': 'rate',
        'tax_code': 'tax_code',
        'uom': 'uom',
    }
    lookup_types = set(lookup_aliases) | {'lookup', 'typeahead', 'autocomplete'}
    if field_type in lookup_types:
        lookup_kind = (
            field_schema.get('lookup_kind')
            or field_schema.get('lookup')
            or lookup_aliases.get(field_type)
            or None
        )
        if lookup_kind:
            lookup_kind = str(lookup_kind).replace('-', '_').lower()
        lookup_model = field_schema.get('lookup_model')
        if not lookup_kind and lookup_model:
            model_key = str(lookup_model).replace('-', '_').lower()
            model_map = {
                'chartofaccount': 'account',
                'account': 'account',
                'vendor': 'vendor',
                'supplier': 'vendor',
                'customer': 'customer',
                'client': 'customer',
                'agent': 'agent',
                'product': 'product',
                'item': 'product',
                'service': 'product',
                'inventoryitem': 'product',
                'warehouse': 'warehouse',
                'taxcode': 'tax_code',
                'costcenter': 'cost_center',
                'department': 'department',
                'project': 'project',
            }
            lookup_kind = model_map.get(model_key)
        lookup_kind = lookup_kind or 'account'
        lookup_url = field_schema.get('lookup_url')
        endpoint = None
        lookup_endpoints = {
            'account': '/accounting/vouchers/htmx/account-lookup/',
            'vendor': '/accounting/generic-voucher/htmx/vendor-lookup/',
            'customer': '/accounting/generic-voucher/htmx/customer-lookup/',
            'agent': '/accounting/journal-entry/lookup/agents/',
            'product': '/accounting/generic-voucher/htmx/product-lookup/',
            'warehouse': '/accounting/journal-entry/lookup/warehouses/',
            'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
            'cost_center': '/accounting/journal-entry/lookup/cost-centers/',
            'department': '/accounting/journal-entry/lookup/departments/',
            'project': '/accounting/journal-entry/lookup/projects/',
        }
        if lookup_url:
            endpoint = lookup_url
        elif lookup_kind in lookup_endpoints:
            endpoint = lookup_endpoints[lookup_kind]
        elif field_type in ('lookup', 'typeahead', 'autocomplete'):
            endpoint = f"/accounting/api/{lookup_kind}/search/"
        
        logger.debug(f"configure_widget_for_schema: Before typeahead modification - widget_class={widget.__class__.__name__}, widget.attrs={widget.attrs}")

        # Replace widget with TypeaheadInput to ensure data attributes persist
        if not isinstance(widget, TypeaheadInput):
            # Preserve existing attributes when replacing widget
            old_attrs = widget.attrs.copy() if hasattr(widget, 'attrs') else {}
            widget = TypeaheadInput(attrs=old_attrs)
        
        base_classes = widget.attrs.get('class', '').strip()
        for cls in ('generic-typeahead', 've-suggest-input', 'typeahead-input'):
            if cls not in base_classes:
                base_classes = f"{base_classes} {cls}".strip()
        
        widget.attrs.update({
            'class': base_classes,
            'data-lookup-kind': str(lookup_kind),
            'autocomplete': 'off',
        })
        if endpoint:
            widget.attrs['data-endpoint'] = endpoint  # Use direct assignment for TypeaheadInput
        if field_name:
            widget.attrs['data-hidden-name'] = field_name  # Use direct assignment for TypeaheadInput
        
        logger.debug(f"Configured typeahead widget for {field_name}: kind={lookup_kind}, endpoint={endpoint}, final_attrs={widget.attrs}")
    
    elif field_type == 'date':
        widget.attrs.setdefault('type', 'date')
        base_classes = widget.attrs.get('class', '').strip()
        if 'date-picker' not in base_classes:
            widget.attrs['class'] = f"{base_classes} date-picker".strip()
    elif field_type == 'datetime':
        widget.attrs.setdefault('type', 'datetime-local')
        base_classes = widget.attrs.get('class', '').strip()
        if 'datetime-picker' not in base_classes:
            widget.attrs['class'] = f"{base_classes} datetime-picker".strip()
    elif field_type in ('number', 'decimal', 'integer'):
        step_val = field_schema.get('step')
        if step_val is None:
            step_val = '1' if field_type == 'integer' else '0.01'
        widget.attrs.setdefault('step', str(step_val))

    return widget


def normalize_ui_schema(ui_schema, *, header_model=None, line_model=None, organization=None):
    """
    Normalize UI schema so UI fields align with what the form builder renders.
    Adds common defaults and ensures typeahead display fields exist.
    """
    schema_copy = copy.deepcopy(ui_schema or {})
    if not isinstance(schema_copy, dict):
        return schema_copy

    schema_root = schema_copy.get('sections') if isinstance(schema_copy.get('sections'), dict) else schema_copy
    if not isinstance(schema_root, dict):
        return schema_copy

    def _get_section_fields(key):
        section = schema_root.get(key)
        if section is None:
            section = {}
            schema_root[key] = section
        if isinstance(section, dict) and isinstance(section.get('fields'), (dict, list)):
            return section['fields'], section
        return section, None

    def _ensure_field(section, name, cfg, wrapper=None):
        if isinstance(section, list):
            if not any(isinstance(it, dict) and it.get('name') == name for it in section):
                section.append({'name': name, **cfg})
            return
        if isinstance(section, dict):
            if name not in section:
                section[name] = cfg
            order_holder = wrapper if isinstance(wrapper, dict) else section
            order = order_holder.setdefault('__order__', [])
            if name not in order:
                order.append(name)

    def _rename_field(section, old_name, new_name, wrapper=None):
        if old_name == new_name:
            return
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict) and item.get('name') == old_name:
                    item['name'] = new_name
                    return
            return
        if isinstance(section, dict):
            if old_name in section:
                section[new_name] = section.pop(old_name)
            order_holder = wrapper if isinstance(wrapper, dict) else section
            order = order_holder.get('__order__', [])
            if order:
                order_holder['__order__'] = [new_name if x == old_name else x for x in order]

    def _iter_fields(section):
        if isinstance(section, dict):
            for name, cfg in section.items():
                if name == '__order__':
                    continue
                if isinstance(cfg, dict):
                    yield name, cfg
        elif isinstance(section, list):
            for item in section:
                if isinstance(item, dict):
                    yield item.get('name') or '', item

    def _is_fk(model, field_name):
        if not model or not field_name:
            return False
        try:
            from django.db import models as dj_models
            model_field = model._meta.get_field(field_name)
            return isinstance(model_field, dj_models.ForeignKey)
        except Exception:
            return False

    header_fields, header_wrapper = _get_section_fields('header')
    lines_fields, lines_wrapper = _get_section_fields('lines')

    if isinstance(header_fields, dict):
        order_holder = header_wrapper if isinstance(header_wrapper, dict) else header_fields
        if '__order__' not in order_holder:
            order_holder['__order__'] = [k for k in header_fields.keys() if k != '__order__']
    if isinstance(lines_fields, dict):
        order_holder = lines_wrapper if isinstance(lines_wrapper, dict) else lines_fields
        if '__order__' not in order_holder:
            order_holder['__order__'] = [k for k in lines_fields.keys() if k != '__order__']

    header_model_fields = set()
    line_model_fields = set()
    try:
        if header_model:
            header_model_fields = {f.name for f in header_model._meta.fields}
    except Exception:
        header_model_fields = set()
    try:
        if line_model:
            line_model_fields = {f.name for f in line_model._meta.fields}
    except Exception:
        line_model_fields = set()

    # Map common aliases to canonical field names without injecting defaults.
    if header_model_fields:
        if 'vendor' in header_model_fields:
            for alias in ('vendor_name', 'supplier'):
                for name, _ in _iter_fields(header_fields):
                    if name == alias:
                        _rename_field(header_fields, alias, 'vendor', header_wrapper)
                        break
        if 'customer' in header_model_fields:
            for alias in ('customer_name', 'client_name'):
                for name, _ in _iter_fields(header_fields):
                    if name == alias:
                        _rename_field(header_fields, alias, 'customer', header_wrapper)
                        break

    # Add display fields for lookup/typeahead or FK-backed fields.
    def _ensure_display_fields(section_fields, wrapper, model):
        if not isinstance(section_fields, (dict, list)):
            return
        for name, cfg in list(_iter_fields(section_fields)):
            if not name or name.endswith('_display'):
                continue
            field_type = (cfg or {}).get('type')
            needs_display = field_type in ('lookup', 'typeahead', 'autocomplete') or _is_fk(model, name)
            if not needs_display:
                continue
            display_name = f"{name}_display"
            _ensure_field(
                section_fields,
                display_name,
                {
                    'label': cfg.get('label') or name.replace('_', ' ').title(),
                    'type': 'char',
                    'required': False,
                    'placeholder': cfg.get('placeholder'),
                },
                wrapper,
            )

    def _ensure_numeric_steps(section_fields):
        if not isinstance(section_fields, (dict, list)):
            return
        for _, cfg in list(_iter_fields(section_fields)):
            if not isinstance(cfg, dict):
                continue
            field_type = (cfg or {}).get('type')
            if field_type in ('number', 'decimal', 'integer') and cfg.get('step') is None:
                cfg['step'] = '1' if field_type == 'integer' else '0.01'

    _ensure_display_fields(header_fields, header_wrapper, header_model)
    _ensure_display_fields(lines_fields, lines_wrapper, line_model)
    _ensure_numeric_steps(header_fields)
    _ensure_numeric_steps(lines_fields)

    return schema_copy


def validate_ui_schema_or_raise(ui_schema: dict) -> None:
    errors = validate_ui_schema(ui_schema or {}, strict_types=True)
    if errors:
        summary = "; ".join(errors[:3])
        if len(errors) > 3:
            summary = f"{summary} (+{len(errors) - 3} more)"
        raise VoucherProcessError("CFG-001", f"Invalid voucher schema: {summary}")

# Minimal dynamic form builder for schema-driven forms

class VoucherFormFactory:
    """
    Generic form factory for voucher configurations.
    Supports UDF injection and default value injection.
    """
    @staticmethod
    def get_journal_form(organization, journal_type=None, instance=None, data=None, files=None, **kwargs):
        form_kwargs = {
            'organization': organization,
            'journal_type': journal_type,
            **kwargs,
        }
        if instance:
            form_kwargs['instance'] = instance
        if data is not None:
            form_kwargs['data'] = data
        if files is not None:
            form_kwargs['files'] = files

        try:
            if organization and journal_type:
                from accounting.models import VoucherModeConfig
                cfg = VoucherModeConfig.objects.filter(
                    organization=organization,
                    journal_type__code=journal_type,
                    is_active=True,
                ).first()
                if cfg:
                    ui = cfg.resolve_ui()
                    if isinstance(ui, dict) and 'header' in ui:
                        form_kwargs['ui_schema'] = ui['header']
        except Exception:
            logger.exception("Failed to load voucher schema for journal form.")

        return JournalForm(**form_kwargs)

    @staticmethod
    def get_journal_line_form(organization, instance=None, data=None, prefix=None, **kwargs):
        form_kwargs = {
            'organization': organization,
            **kwargs,
        }
        if instance:
            form_kwargs['instance'] = instance
        if data is not None:
            form_kwargs['data'] = data
        if prefix:
            form_kwargs['prefix'] = prefix

        try:
            from accounting.models import VoucherModeConfig
            cfg = None
            journal_type = kwargs.get('journal_type')
            if organization and journal_type:
                cfg = VoucherModeConfig.objects.filter(
                    organization=organization,
                    journal_type__code=journal_type,
                    is_active=True,
                ).first()
            elif organization and instance and getattr(instance, 'journal', None):
                cfg = VoucherModeConfig.objects.filter(
                    organization=organization,
                    journal_type=getattr(instance.journal, 'journal_type', None),
                    is_active=True,
                ).first()
            if cfg:
                ui = cfg.resolve_ui()
                if isinstance(ui, dict) and 'lines' in ui:
                    form_kwargs['ui_schema'] = ui['lines']
        except Exception:
            logger.exception("Failed to load voucher schema for journal line form.")

        return JournalLineForm(**form_kwargs)

    @staticmethod
    def get_journal_line_formset(organization, journal=None, data=None, prefix=None, **kwargs):
        form_kwargs = {
            'organization': organization,
            **kwargs,
        }
        if data is not None:
            form_kwargs['data'] = data
        if prefix:
            form_kwargs['prefix'] = prefix
        if journal is not None:
            form_kwargs['instance'] = journal

        try:
            journal_type = getattr(journal, 'journal_type', None) if journal else kwargs.get('journal_type')
            if organization and journal_type:
                from accounting.models import VoucherModeConfig
                cfg = VoucherModeConfig.objects.filter(
                    organization=organization,
                    journal_type=journal_type,
                    is_active=True,
                ).first()
                if cfg:
                    ui = cfg.resolve_ui()
                    if isinstance(ui, dict) and 'lines' in ui:
                        form_kwargs['ui_schema'] = ui['lines']
        except Exception:
            logger.exception("Failed to load voucher schema for journal line formset.")

        return JournalLineFormSet(**form_kwargs)

    @staticmethod
    def create_blank_line_form(organization, form_index=0, journal_type=None):
        prefix = f'lines-{form_index}'
        return VoucherFormFactory.get_journal_line_form(
            organization=organization,
            prefix=prefix,
            journal_type=journal_type,
        )

    @staticmethod
    def validate_forms(header_form, line_formset):
        header_valid = header_form.is_valid()
        lines_valid = line_formset.is_valid()
        errors = {}
        if not header_valid:
            errors['header'] = header_form.errors
        if not lines_valid:
            errors['lines'] = line_formset.errors
        return header_valid and lines_valid, errors

    @staticmethod
    def _get_model_for_voucher_config(voucher_config):
        """Resolve the header model for a voucher config. Defaults to Journal."""
        return Journal

    @staticmethod
    def _get_line_model_for_voucher_config(voucher_config):
        """Resolve the line model for a voucher config. Defaults to JournalLine."""
        return JournalLine

    def __init__(self, configuration, model=None, organization=None, user_perms=None, prefix=None,
                 phase=None, initial=None, disabled_fields=None, normalized=False, **kwargs):
        self.original_configuration = configuration  # Store original config object
        self.configuration = configuration
        if hasattr(configuration, 'resolve_ui_schema'):
            self.schema = configuration.resolve_ui_schema()
        elif isinstance(configuration, dict):
            self.schema = configuration  # Handle direct schema dicts.
        else:
            self.schema = {}
        self.model = model
        self.organization = organization
        self.user_perms = user_perms
        self.prefix = prefix
        self.phase = phase
        self.initial = initial or {}
        # Inject default values from configuration
        if hasattr(configuration, 'default_header') and configuration.default_header:
            self.initial.update(configuration.default_header)
        # Default dynamic form 'currency' initial to organization's base currency.
        try:
            if self.organization is not None:
                base_cur = getattr(self.organization, 'base_currency_code_id', None) or getattr(self.organization, 'base_currency_code', None)
                if base_cur:
                    if self.model:
                        try:
                            from django.db import models as dj_models
                            field = None
                            try:
                                field = self.model._meta.get_field('currency')
                            except Exception:
                                field = None
                            if field is not None and isinstance(field, dj_models.ForeignKey):
                                currency_id = None
                                if hasattr(base_cur, 'pk'):
                                    currency_id = base_cur.pk
                                elif isinstance(base_cur, int):
                                    currency_id = base_cur
                                elif isinstance(base_cur, str):
                                    try:
                                        from accounting.models import Currency
                                        currency_id = Currency.objects.filter(currency_code=base_cur).values_list('pk', flat=True).first()
                                    except Exception:
                                        currency_id = None
                                if currency_id is not None:
                                    self.initial.setdefault('currency', currency_id)
                            elif field is not None:
                                self.initial.setdefault('currency', base_cur)
                            else:
                                try:
                                    self.model._meta.get_field('currency_code')
                                    code_val = getattr(base_cur, 'currency_code', None) or getattr(base_cur, 'pk', None) or base_cur
                                    if code_val is not None:
                                        self.initial.setdefault('currency_code', code_val)
                                except Exception:
                                    self.initial.setdefault('currency', base_cur)
                        except Exception:
                            self.initial.setdefault('currency', base_cur)
                    else:
                        self.initial.setdefault('currency', base_cur)
        except Exception:
            pass
        self.disabled_fields = disabled_fields or []
        self.normalized = normalized
        self.kwargs = kwargs

    def _create_field_from_schema(self, config, field_name=None):
        """Create a form field from a schema definition."""
        field_type = config.get('type') or config.get('field_type', 'char')
        field_class = self._map_type_to_field(field_type)
        
        field_kwargs = {
            'label': config.get('label'),
            'required': config.get('required', True),
            'help_text': config.get('help_text'),
            'min_length': config.get('min_length'),
            'max_length': config.get('max_length'),
        }
        validators = []
        pattern = config.get('pattern') or config.get('regex')
        if pattern:
            try:
                from django.core.validators import RegexValidator
                validators.append(RegexValidator(pattern))
            except Exception:
                pass
        if validators:
            field_kwargs['validators'] = validators

        if field_type in ('number', 'decimal', 'integer'):
            if 'min_value' in config:
                field_kwargs['min_value'] = config.get('min_value')
            if 'max_value' in config:
                field_kwargs['max_value'] = config.get('max_value')
        
        # Handle default value
        if 'default' in config:
            field_kwargs['initial'] = config['default']
        
        # If field is read_only, make it not required and ensure it has initial value
        if config.get('read_only') or config.get('disabled'):
            field_kwargs['required'] = False
            if 'initial' not in field_kwargs and 'default' in config:
                field_kwargs['initial'] = config['default']

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
        
        # Apply field-level schema flags BEFORE widget creation (autofocus, placeholder, etc.)
        placeholder = config.get('placeholder')
        if placeholder:
            attrs['placeholder'] = placeholder
        if config.get('autofocus'):
            attrs['autofocus'] = 'autofocus'

        widget_class = self._map_type_to_widget(field_type)
        if widget_class:
            if widget_class is DualCalendarWidget:
                default_view = get_calendar_mode(
                    self.organization, default=CalendarMode.DUAL
                )
                widget = widget_class(
                    default_view=default_view,
                    attrs=attrs,
                )
                field_kwargs['widget'] = configure_widget_for_schema(field_name, config, widget)
            else:
                widget = widget_class(attrs=attrs)
                field_kwargs['widget'] = configure_widget_for_schema(field_name, config, widget)
        elif attrs:  # Fallback for fields without specific widget mapping but with attrs
            widget = forms.TextInput(attrs=attrs)
            field_kwargs['widget'] = configure_widget_for_schema(field_name, config, widget)

        if field_type == 'select':
            choices = config.get('choices', [])
            from django.apps import apps
            if isinstance(choices, str):
                # Treat as a model reference, use ModelChoiceField with queryset
                try:
                    model = apps.get_model('accounting', choices)
                    model_field = None
                    if self.model is not None and field_name:
                        try:
                            model_field = self.model._meta.get_field(field_name)
                        except Exception:
                            model_field = None
                    queryset = model.objects.all()
                    # Only filter by is_active if the model has this field
                    if hasattr(model, 'is_active'):
                        queryset = queryset.filter(is_active=True)
                    if model_field is not None:
                        try:
                            from django.db import models as dj_models
                            if isinstance(model_field, dj_models.ForeignKey):
                                field_class = forms.ModelChoiceField
                                field_kwargs['queryset'] = queryset
                                field_kwargs['to_field_name'] = getattr(model._meta.pk, 'name', 'id')
                            else:
                                field_class = forms.ChoiceField
                                field_kwargs['choices'] = [(obj.pk, str(obj)) for obj in queryset]
                        except Exception:
                            field_class = forms.ChoiceField
                            field_kwargs['choices'] = [(obj.pk, str(obj)) for obj in queryset]
                    else:
                        field_class = forms.ModelChoiceField
                        field_kwargs['queryset'] = queryset
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

        # Apply field-level schema flags (hidden/disabled/read_only)
        if config.get('hidden'):
            from django.forms import widgets
            field_kwargs['widget'] = widgets.HiddenInput(attrs=attrs)
        if config.get('disabled') or config.get('read_only'):
            field_kwargs['disabled'] = True
            attrs['readonly'] = 'readonly'

        # If this is a well-known lookup field but not modeled as FK, still attach suggest metadata
        def _canonical_lookup_kind(name: str):
            key = (name or '').replace('-', '_').lower()
            aliases = {
                'account': {'account', 'gl_account', 'ledger', 'chartofaccount'},
                'vendor': {'vendor', 'supplier'},
                'customer': {'customer', 'client'},
                'agent': {'agent'},
                'product': {'product', 'item', 'service', 'inventoryitem', 'inventory_item'},
                'warehouse': {'warehouse'},
                'tax_code': {'tax_code', 'taxcode'},
                'cost_center': {'cost_center'},
                'department': {'department'},
                'project': {'project'},
            }
            for canon, names in aliases.items():
                if key in names:
                    return canon
                for suffix in ('_id', '_code', '_name', '_display'):
                    if key.endswith(suffix) and key[:-len(suffix)] in names:
                        return canon
            return None

        lookup_endpoints = {
            'account': '/accounting/vouchers/htmx/account-lookup/',
            'vendor': '/accounting/generic-voucher/htmx/vendor-lookup/',
            'customer': '/accounting/generic-voucher/htmx/customer-lookup/',
            'agent': '/accounting/journal-entry/lookup/agents/',
            'product': '/accounting/generic-voucher/htmx/product-lookup/',
            'warehouse': '/accounting/journal-entry/lookup/warehouses/',
            'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
            'cost_center': '/accounting/journal-entry/lookup/cost-centers/',
            'department': '/accounting/journal-entry/lookup/departments/',
            'project': '/accounting/journal-entry/lookup/projects/',
        }
        lookup_override = config.get('lookup_url')

        canonical_kind = _canonical_lookup_kind(field_name or '')
        if canonical_kind in lookup_endpoints and not isinstance(field_kwargs.get('widget'), forms.HiddenInput):
            attrs.setdefault('autocomplete', 'off')
            endpoint = lookup_endpoints[canonical_kind]
            if lookup_override:
                try:
                    from django.urls import reverse
                    endpoint = reverse(lookup_override)
                except Exception:
                    endpoint = lookup_override
            attrs.setdefault('data-endpoint', endpoint)
            hidden_name = field_name
            if field_name and field_name.endswith('_display'):
                hidden_name = field_name[:-8]
            attrs.setdefault('data-hidden-name', hidden_name)
            attrs.setdefault('data-lookup-kind', canonical_kind.replace('_', ''))
            base_classes = attrs.get('class', '').strip()
            if 've-suggest-input' not in base_classes:
                attrs['class'] = f"{base_classes} ve-suggest-input generic-typeahead".strip()
            field_kwargs['widget'] = TypeaheadInput(attrs=attrs)

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
        # Broaden support for lookup-enabled FKs (synonyms map to canonical kinds)
        lookup_kind_map = {
            'ChartOfAccount': 'account',
            'Account': 'account',
            'Vendor': 'vendor',
            'Supplier': 'vendor',
            'Customer': 'customer',
            'Client': 'customer',
            'Product': 'product',
            'Item': 'product',
            'Service': 'product',
            'InventoryItem': 'product',
            'CostCenter': 'costcenter',
            'Department': 'department',
            'Project': 'project',
            'TaxCode': 'taxcode',
        }

        if related_name not in lookup_kind_map:
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
            'ChartOfAccount': '/accounting/journal-entry/lookup/accounts/',
            'Account': '/accounting/journal-entry/lookup/accounts/',
            'CostCenter': '/accounting/journal-entry/lookup/cost-centers/',
            'Department': '/accounting/journal-entry/lookup/departments/',
            'Project': '/accounting/journal-entry/lookup/projects/',
            'TaxCode': '/accounting/journal-entry/lookup/tax-codes/',
            'Vendor': '/accounting/journal-entry/lookup/vendors/',
            'Supplier': '/accounting/journal-entry/lookup/vendors/',
            'Customer': '/accounting/journal-entry/lookup/customers/',
            'Client': '/accounting/journal-entry/lookup/customers/',
            'Product': '/accounting/journal-entry/lookup/products/',
            'Item': '/accounting/journal-entry/lookup/products/',
            'Service': '/accounting/journal-entry/lookup/products/',
            'InventoryItem': '/accounting/journal-entry/lookup/products/',
        }
        endpoint_override = config.get('lookup_url')
        endpoint = endpoint_map.get(related_name, '')
        if endpoint_override:
            try:
                from django.urls import reverse
                endpoint = reverse(endpoint_override)
            except Exception:
                endpoint = endpoint_override
        base_classes = 'form-control generic-typeahead ve-suggest-input'
        display_attrs = {
            'class': base_classes,
            'autocomplete': 'off',
            'data-endpoint': endpoint,
            'data-hidden-name': field_name,
            'data-lookup-kind': lookup_kind_map.get(related_name, related_name.lower()),
            'data-add-url': {
                'ChartOfAccount': '/accounting/chart-of-accounts/create/',
                'Account': '/accounting/chart-of-accounts/create/',
                'CostCenter': '/accounting/cost-centers/create/',
                'Department': '/accounting/departments/create/',
                'Project': '/accounting/projects/create/',
                'TaxCode': '/accounting/tax-codes/create/',
                'Vendor': '/accounting/vendors/new/',
                'Supplier': '/accounting/vendors/new/',
                'Customer': '/accounting/customers/new/',
                'Client': '/accounting/customers/new/',
                'Product': '/inventory/products/create/',
                'Item': '/inventory/products/create/',
                'Service': '/inventory/products/create/',
                'InventoryItem': '/inventory/products/create/',
            }.get(related_name, ''),
        }
        placeholder = config.get('placeholder')
        if placeholder:
            display_attrs['placeholder'] = placeholder
        if related_name == 'ChartOfAccount':
            display_attrs['class'] = base_classes.replace('generic-typeahead', 'account-typeahead')

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
            'textarea': forms.CharField,
            'date': forms.DateField,
            'bsdate': forms.DateField,
            'datetime': forms.DateTimeField,
            'decimal': forms.DecimalField,
            'number': forms.DecimalField,
            'integer': forms.IntegerField,
            'boolean': forms.BooleanField,
            'checkbox': forms.BooleanField,
            'select': forms.ChoiceField,
            'account': forms.ModelChoiceField,
            'party': forms.CharField,
            'customer': forms.CharField,
            'vendor': forms.CharField,
            'product': forms.CharField,
            'warehouse': forms.CharField,
            'cost_center': forms.CharField,
            'department': forms.CharField,
            'project': forms.CharField,
            'journal_type': forms.CharField,
            'period': forms.CharField,
            'currency': forms.CharField,
            'rate': forms.CharField,
            'tax_code': forms.CharField,
            'uom': forms.CharField,
            'lookup': forms.CharField,
            'typeahead': forms.CharField,
            'autocomplete': forms.CharField,
        }
        return type_map.get(field_type, forms.CharField)

    def _map_type_to_widget(self, field_type):
        """Map schema field type to a Django Form Widget."""
        widget_map = {
            'text': forms.Textarea,
            'textarea': forms.Textarea,
            'date': DualCalendarWidget,
            'datetime': forms.DateTimeInput,
            'account': AccountChoiceWidget,
            'select': forms.Select,
            'lookup': forms.TextInput,
            'typeahead': forms.TextInput,
            'autocomplete': forms.TextInput,
            'number': forms.NumberInput,
            'decimal': forms.NumberInput,
            'integer': forms.NumberInput,
            'integer': forms.NumberInput,
            'checkbox': forms.CheckboxInput,
            'bsdate': DualCalendarWidget,
        }
        return widget_map.get(field_type)

    def build_form(self):
        """Dynamically build and return a Form class based on the configuration's ui_schema."""
        form_fields = {}
        schema = self.configuration.resolve_ui_schema() if hasattr(self.configuration, 'resolve_ui_schema') else self.schema
        skip_fields = set()

        # Unwrap "sections" if present (e.g., {"sections": {"header": {...}}})
        if isinstance(schema, dict) and 'sections' in schema:
            schema = schema['sections']

        # Support ui_schema that contains top-level 'header'/'lines' sections.
        # When building a header form, prefer the 'header' section if present.
        if isinstance(schema, dict) and ('header' in schema or 'lines' in schema):
            # Prefer header when available; fallback to lines only when header missing.
            header_section = schema.get('header')
            if header_section is not None:
                schema = header_section
            else:
                schema = schema.get('lines')
        
        # If schema has a 'fields' key, extract it (e.g., {"fields": {...}})
        if isinstance(schema, dict) and 'fields' in schema and isinstance(schema.get('fields'), dict):
            # Preserve __order__ if present at the parent level
            order = schema.get('__order__')
            schema = schema['fields']
            if order and '__order__' not in schema:
                schema['__order__'] = order

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
            display_configs = {
                it.get('name') or it.get('key'): it for it in list_items if isinstance(it, dict) and (it.get('name') or it.get('key'))
            }
            if any(isinstance(it, dict) and 'order_no' in it for it in list_items):
                try:
                    list_items = sorted(list_items, key=lambda it: it.get('order_no', 9999) if isinstance(it, dict) else 9999)
                except Exception:
                    pass
            for field_config in list_items:
                field_name = field_config.get('name') or field_config.get('key')
                if not field_name:
                    continue
                if field_name in skip_fields:
                    continue
                fk_pair = self._maybe_build_fk_typeahead_fields(field_name, field_config)
                if fk_pair:
                    base_field, display_field = fk_pair
                    form_fields[field_name] = base_field
                    display_name = f"{field_name}_display"
                    display_config = display_configs.get(display_name)
                    if display_config:
                        form_fields[display_name] = self._create_field_from_schema(display_config, field_name=display_name)
                        skip_fields.add(display_name)
                    else:
                        form_fields[display_name] = display_field
                else:
                    form_fields[field_name] = self._create_field_from_schema(field_config, field_name=field_name)
        elif isinstance(schema, dict):
            if 'fields' in schema and isinstance(schema['fields'], list):
                field_list = list(schema['fields'])
                display_configs = {
                    it.get('name'): it for it in field_list if isinstance(it, dict) and it.get('name')
                }
                if any(isinstance(it, dict) and 'order_no' in it for it in field_list):
                    try:
                        field_list = sorted(field_list, key=lambda it: it.get('order_no', 9999) if isinstance(it, dict) else 9999)
                    except Exception:
                        pass
                for field_config in field_list:
                    field_name = field_config.get('name')
                    if field_name:
                        if field_name in skip_fields:
                            continue
                        fk_pair = self._maybe_build_fk_typeahead_fields(field_name, field_config)
                        if fk_pair:
                            base_field, display_field = fk_pair
                            form_fields[field_name] = base_field
                            display_name = f"{field_name}_display"
                            display_config = display_configs.get(display_name)
                            if display_config:
                                form_fields[display_name] = self._create_field_from_schema(display_config, field_name=display_name)
                                skip_fields.add(display_name)
                            else:
                                form_fields[display_name] = display_field
                        else:
                            form_fields[field_name] = self._create_field_from_schema(field_config, field_name=field_name)
            else:  # Assume schema is a direct dictionary of field_name: field_config
                for field_name, field_config in _ordered_schema_items(schema):
                    if field_name in skip_fields:
                        continue
                    fk_pair = self._maybe_build_fk_typeahead_fields(field_name, field_config)
                    if fk_pair:
                        base_field, display_field = fk_pair
                        form_fields[field_name] = base_field
                        display_name = f"{field_name}_display"
                        display_config = schema.get(display_name) if isinstance(schema.get(display_name), dict) else None
                        if display_config:
                            form_fields[display_name] = self._create_field_from_schema(display_config, field_name=display_name)
                            skip_fields.add(display_name)
                        else:
                            form_fields[display_name] = display_field
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

            def clean(self):
                """Validate form data including cross-field validations."""
                cleaned_data = super().clean()
                
                # Header-level validations
                if hasattr(self.form_factory, 'configuration') and hasattr(self.form_factory, 'organization'):
                    from accounting.services.validation_service import ValidationService
                    
                    # For header forms
                    if not getattr(self.form_factory, 'phase', None) or self.form_factory.phase == 'header':
                        errors = ValidationService.validate_voucher_header(
                            cleaned_data, 
                            self.form_factory.original_configuration, 
                            self.form_factory.organization
                        )
                        for field, error in errors.items():
                            if field in self.fields:
                                self.add_error(field, error)
                    
                    # For line forms
                    elif self.form_factory.phase == 'lines':
                        line_index = getattr(self, 'line_index', 1)
                        errors = ValidationService.validate_voucher_line(
                            cleaned_data,
                            self.form_factory.original_configuration,
                            self.form_factory.organization,
                            line_index
                        )
                        for field, error in errors.items():
                            if field in self.fields:
                                self.add_error(field, error)
                    
                    # For additional charges
                    elif self.form_factory.phase == 'additional_charges':
                        # Additional charges validation would be handled at formset level
                        pass
                
                return cleaned_data
            
            def save(self, commit=True):
                if self.form_factory.model:
                    # This is a ModelForm, save with alias mapping for common header dates.
                    instance = super().save(commit=False)

                    try:
                        voucher_date = self.cleaned_data.get('voucher_date')
                        if voucher_date:
                            if hasattr(instance, 'order_date') and not getattr(instance, 'order_date', None):
                                instance.order_date = voucher_date
                            if hasattr(instance, 'invoice_date') and not getattr(instance, 'invoice_date', None):
                                instance.invoice_date = voucher_date
                        order_date = self.cleaned_data.get('order_date')
                        if order_date and hasattr(instance, 'voucher_date') and not getattr(instance, 'voucher_date', None):
                            instance.voucher_date = order_date
                        invoice_date = self.cleaned_data.get('invoice_date')
                        if invoice_date and hasattr(instance, 'voucher_date') and not getattr(instance, 'voucher_date', None):
                            instance.voucher_date = invoice_date
                        journal_date = self.cleaned_data.get('journal_date')
                        if journal_date and hasattr(instance, 'voucher_date') and not getattr(instance, 'voucher_date', None):
                            instance.voucher_date = journal_date
                        receipt_date = self.cleaned_data.get('receipt_date')
                        if receipt_date and hasattr(instance, 'voucher_date') and not getattr(instance, 'voucher_date', None):
                            instance.voucher_date = receipt_date
                    except Exception:
                        pass

                    # Apply base currency when the model expects currency data but the form omitted it.
                    try:
                        organization = getattr(self.form_factory, 'organization', None)
                        base_cur = None
                        if organization is not None:
                            base_cur = getattr(organization, 'base_currency_code', None) or getattr(organization, 'base_currency_code_id', None)
                        if base_cur:
                            try:
                                from django.db import models as dj_models
                                field = None
                                try:
                                    field = instance._meta.get_field('currency')
                                except Exception:
                                    field = None
                                if field is not None and isinstance(field, dj_models.ForeignKey):
                                    if not getattr(instance, 'currency_id', None):
                                        currency_id = None
                                        if hasattr(base_cur, 'pk'):
                                            currency_id = base_cur.pk
                                        elif isinstance(base_cur, int):
                                            currency_id = base_cur
                                        elif isinstance(base_cur, str):
                                            currency_id = base_cur
                                        if currency_id is not None:
                                            instance.currency_id = currency_id
                                elif field is not None:
                                    if not getattr(instance, 'currency', None):
                                        instance.currency = base_cur
                            except Exception:
                                pass
                            if hasattr(instance, 'currency_code') and not getattr(instance, 'currency_code', None):
                                code_val = getattr(base_cur, 'currency_code', None) or getattr(base_cur, 'pk', None) or base_cur
                                if code_val is not None:
                                    instance.currency_code = code_val
                    except Exception:
                        pass

                    # Persist extra schema fields into udf_data if available
                    try:
                        def _udf_serialize(value):
                            if value is None:
                                return None
                            try:
                                from django.db import models as dj_models
                                if isinstance(value, dj_models.Model):
                                    return value.pk
                            except Exception:
                                pass
                            try:
                                from decimal import Decimal
                                if isinstance(value, Decimal):
                                    return str(value)
                            except Exception:
                                pass
                            try:
                                import datetime
                                if isinstance(value, (datetime.date, datetime.datetime)):
                                    return value.isoformat()
                            except Exception:
                                pass
                            if isinstance(value, dict):
                                return {k: _udf_serialize(v) for k, v in value.items()}
                            if isinstance(value, (list, tuple)):
                                return [_udf_serialize(v) for v in value]
                            return value

                        if hasattr(instance, 'udf_data') and isinstance(instance.udf_data, dict):
                            extra = {
                                k: _udf_serialize(self.cleaned_data.get(k))
                                for k in self.cleaned_data.keys()
                                if k not in model_field_names and not k.endswith('_display')
                            }
                            if extra:
                                instance.udf_data.update(extra)
                    except Exception:
                        pass

                    # Map common item aliases onto voucher line models.
                    try:
                        if hasattr(instance, 'quantity_ordered') and self.cleaned_data.get('quantity') is not None:
                            if not getattr(instance, 'quantity_ordered', None):
                                instance.quantity_ordered = self.cleaned_data.get('quantity')
                        if hasattr(instance, 'product_name') and self.cleaned_data.get('item'):
                            if not getattr(instance, 'product_name', None):
                                instance.product_name = self.cleaned_data.get('item')
                    except Exception:
                        pass

                    if commit:
                        instance.save()
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
        # If this factory was constructed with a config (self.schema is the UI dict),
        # we must avoid build_form() picking the header section. Build a temporary factory using
        # only the 'lines' schema so the line form fields are correct.
        LineForm = None
        if isinstance(self.schema, dict) and 'lines' in self.schema:
            lines_schema = copy.deepcopy(self.schema.get('lines') or {})

            if not self.normalized:
                # Augment lines schema with required model fields when missing (to avoid validation/DB errors)
                line_model_fields = set()
                try:
                    if self.model:
                        line_model_fields = {f.name for f in self.model._meta.fields}
                except Exception:
                    line_model_fields = set()

                def ensure_line_field(name, cfg):
                    if isinstance(lines_schema, list):
                        if not any(isinstance(it, dict) and it.get('name') == name for it in lines_schema):
                            lines_schema.append({'name': name, **cfg})
                    elif isinstance(lines_schema, dict):
                        if name not in lines_schema:
                            lines_schema[name] = cfg

                numeric_cfg = lambda default_val='0': {'label': '', 'type': 'decimal', 'required': False, 'order_no': 9999, 'kwargs': {'widget': {'attrs': {'value': default_val}}}}

                if 'line_number' in line_model_fields:
                    ensure_line_field(
                        'line_number',
                        {
                            'label': 'Line #',
                            'type': 'integer',
                            'required': False,
                            'order_no': 0,
                            'hidden': True,
                        },
                    )
                if 'account' in line_model_fields:
                    ensure_line_field('account', {'label': 'Account', 'type': 'char', 'required': False, 'order_no': 1})
                for amt_field in ['debit', 'credit', 'amount', 'tax_amount', 'debit_amount', 'credit_amount', 'amount_txn', 'amount_base', 'functional_debit_amount', 'functional_credit_amount']:
                    if amt_field in line_model_fields:
                        ensure_line_field(amt_field, numeric_cfg())

                # Enforce a sensible visual column order for lines: S.No, Account, Description,
                # Debit/Credit/Amount, Cost Center (if present). This ensures UI consistency
                # regardless of how the schema was authored.
                desired_seq = [
                    'line_number',
                    'account',
                    'description',
                    'debit', 'debit_amount',
                    'credit', 'credit_amount',
                    'amount',
                    'cost_center',
                ]

                # If lines_schema is a dict, set explicit __order__ to prefer desired_seq
                if isinstance(lines_schema, dict):
                    order = []
                    existing_keys = [k for k in lines_schema.keys() if k != '__order__']
                    # Add fields in desired order if they exist in the schema or model
                    for name in desired_seq:
                        if name in lines_schema and name not in order:
                            order.append(name)
                    # Append remaining fields preserving their original order
                    for name in existing_keys:
                        if name not in order:
                            order.append(name)
                    if order:
                        lines_schema['__order__'] = order

                # If lines_schema is a list, reorder the list entries according to desired_seq
                elif isinstance(lines_schema, list):
                    # Build a map name->item for quick lookup
                    item_map = { (it.get('name') if isinstance(it, dict) else None): it for it in lines_schema }
                    reordered = []
                    for name in desired_seq:
                        if name in item_map and item_map[name] not in reordered:
                            reordered.append(item_map[name])
                    # Append any remaining items preserving original relative order
                    for it in lines_schema:
                        if it not in reordered:
                            reordered.append(it)
                    lines_schema[:] = reordered

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

            def clean(self):
                """Validate formset data including cross-formset validations."""
                super().clean()
                
                # Check that at least one form is valid and not deleted
                if hasattr(self.form_factory, 'configuration') and hasattr(self.form_factory, 'organization'):
                    from accounting.services.validation_service import ValidationService
                    
                    # For line formsets
                    if getattr(self.form_factory, 'phase', None) == 'lines':
                        valid_forms = 0
                        for form in self.forms:
                            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                                valid_forms += 1
                        
                        if valid_forms == 0:
                            raise forms.ValidationError("At least one voucher line is required.")
                    
                    # For additional charges formsets
                    elif getattr(self.form_factory, 'phase', None) == 'additional_charges':
                        charges_data = []
                        for form in self.forms:
                            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                                charges_data.append(form.cleaned_data)
                        
                        if charges_data:
                            errors = ValidationService.validate_additional_charges(
                                charges_data,
                                self.form_factory.original_configuration,
                                self.form_factory.organization
                            )
                            for field, error in errors.items():
                                self.add_error(field, error)
        
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
        # The authoritative mapping lives in `accounting.forms_factory`.
        try:
            header_model = VoucherFormFactory._get_model_for_voucher_config(voucher_config)
            form_kwargs['model'] = header_model
        except Exception:
            pass
        resolved_schema = voucher_config.resolve_ui_schema() if hasattr(voucher_config, 'resolve_ui_schema') else {}
        validate_ui_schema_or_raise(resolved_schema)
        normalized_schema = normalize_ui_schema(
            resolved_schema,
            header_model=form_kwargs.get('model'),
            line_model=None,
            organization=organization,
        )
        form_kwargs['configuration'] = normalized_schema

        factory = VoucherFormFactory(normalized=True, **form_kwargs)
        return factory.build_form()

    @staticmethod
    def build(voucher_config, organization, *, instance=None, data=None, files=None, **kwargs):
        """
        Unified public entry point for voucher form generation.
        Returns (header_form_class, line_formset_class) or 
        (header_form_class, line_formset_class, additional_charges_formset_class) if schema has additional_charges.
        """
        header_form_cls = VoucherFormFactory.get_generic_voucher_form(
            voucher_config=voucher_config,
            organization=organization,
            instance=instance,
            data=data,
            files=files,
            **kwargs,
        )
        line_formset_cls = VoucherFormFactory.get_generic_voucher_formset(
            voucher_config=voucher_config,
            organization=organization,
            instance=instance,
            data=data,
            files=files,
            **kwargs,
        )
        
        # Check if schema has additional_charges section
        ui_schema = getattr(voucher_config, 'schema_definition', None) or {}
        if isinstance(ui_schema, str):
            import json
            try:
                ui_schema = json.loads(ui_schema)
            except (json.JSONDecodeError, TypeError):
                ui_schema = {}
        
        if 'additional_charges' in ui_schema:
            additional_charges_formset_cls = VoucherFormFactory.get_additional_charges_formset(
                voucher_config=voucher_config,
                organization=organization,
                data=data,
                files=files,
                **kwargs,
            )
            return header_form_cls, line_formset_cls, additional_charges_formset_cls
        
        return header_form_cls, line_formset_cls
    
    @staticmethod
    def get_additional_charges_formset(voucher_config, organization, *, data=None, files=None, **kwargs):
        """
        Build a formset for additional charges based on schema definition.
        """
        ui_schema = getattr(voucher_config, 'schema_definition', None) or {}
        if isinstance(ui_schema, str):
            import json
            try:
                ui_schema = json.loads(ui_schema)
            except (json.JSONDecodeError, TypeError):
                ui_schema = {}
        
        additional_charges_schema = ui_schema.get('additional_charges', {})
        if not additional_charges_schema:
            return None
        if isinstance(additional_charges_schema, list):
            from accounting.voucher_schema import definition_to_ui_schema
            additional_charges_schema = definition_to_ui_schema(
                {"header_fields": additional_charges_schema}
            ).get("header", {})

        # Create a config object for the additional charges section
        class AdditionalChargesConfig:
            def __init__(self, schema):
                self.schema_definition = {'header': schema}

            def resolve_ui_schema(self):
                return self.schema_definition
        
        ac_config = AdditionalChargesConfig(additional_charges_schema)
        
        factory = VoucherFormFactory(
            configuration=ac_config,
            organization=organization,
            prefix='additional_charges',
            phase='additional_charges',
        )
        form_cls = factory.build_form()
        
        # Create a formset from this form class
        from django.forms import formset_factory
        formset_cls = formset_factory(
            form_cls,
            extra=1,
            can_delete=True,
        )
        return formset_cls

    @staticmethod
    def get_payment_receipt_formset(organization, *, data=None, files=None, **kwargs):
        """
        Create a formset for payment receipts integrated with vouchers.
        """
        payment_schema = {
            'header': {
                'payment_date': {
                    'label': 'Payment Date',
                    'type': 'date',
                    'required': True,
                    'order_no': 1
                },
                'exchange_rate': {
                    'label': 'Exchange Rate',
                    'type': 'decimal',
                    'required': False,
                    'order_no': 2,
                    'step': '0.01',
                    'min': '0.01'
                },
                'account': {
                    'label': 'Payment Account',
                    'type': 'lookup',
                    'lookup_kind': 'account',
                    'required': True,
                    'order_no': 3
                },
                'payment_method': {
                    'label': 'Payment Method',
                    'type': 'select',
                    'required': True,
                    'order_no': 4,
                    'choices': [
                        ('cash', 'Cash'),
                        ('bank_transfer', 'Bank Transfer'),
                        ('cheque', 'Cheque'),
                        ('credit_card', 'Credit Card'),
                        ('other', 'Other')
                    ]
                },
                'amount': {
                    'label': 'Amount',
                    'type': 'decimal',
                    'required': True,
                    'order_no': 5,
                    'step': '0.01',
                    'min': '0.01'
                },
                'currency': {
                    'label': 'Currency',
                    'type': 'select',
                    'required': False,
                    'order_no': 6
                },
                'reference': {
                    'label': 'Reference',
                    'type': 'char',
                    'required': False,
                    'order_no': 7,
                    'max_length': 50
                }
            }
        }

        # Create a config object for the payment formset
        class PaymentConfig:
            def __init__(self, schema):
                self.schema_definition = schema

            def resolve_ui_schema(self):
                return self.schema_definition

        payment_config = PaymentConfig(payment_schema)

        factory = VoucherFormFactory(
            configuration=payment_config,
            organization=organization,
            prefix='payments',
            phase='payments',
        )
        form_cls = factory.build_form()

        # Create a formset from this form class
        from django.forms import formset_factory
        formset_cls = formset_factory(
            form_cls,
            extra=1,
            can_delete=True,
        )

        class PaymentFormSet(formset_cls):
            def clean(self):
                """Validate payment formset data."""
                super().clean()

                if hasattr(self, 'voucher_total'):
                    from accounting.services.validation_service import ValidationService
                    payments_data = []
                    for form in self.forms:
                        if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                            payments_data.append(form.cleaned_data)

                    if payments_data:
                        errors = ValidationService.validate_payment_receipt(
                            payments_data,
                            self.voucher_total,
                            factory.organization
                        )
                        for field, error in errors.items():
                            self.add_error(field, error)

        return PaymentFormSet

    @staticmethod
    def get_generic_voucher_formset(voucher_config, organization, instance=None, data=None, files=None, **kwargs):
        """
        Create a generic voucher line formset.
        """
        form_kwargs = {
            'configuration': voucher_config,
            'organization': organization,
            'prefix': 'lines',
            **kwargs
        }

        # Provide the line model to the factory so line-specific fields (FKs/typeaheads)
        # can be constructed correctly when building the line forms.
        try:
            line_model = VoucherFormFactory._get_line_model_for_voucher_config(voucher_config)
            form_kwargs['model'] = line_model
        except Exception:
            pass
        
        if data is not None:
            form_kwargs['data'] = data
        if files is not None:
            form_kwargs['files'] = files
        
        resolved_schema = voucher_config.resolve_ui_schema() if hasattr(voucher_config, 'resolve_ui_schema') else {}
        validate_ui_schema_or_raise(resolved_schema)
        normalized_schema = normalize_ui_schema(
            resolved_schema,
            header_model=None,
            line_model=form_kwargs.get('model'),
            organization=organization,
        )
        form_kwargs['configuration'] = normalized_schema

        factory = VoucherFormFactory(normalized=True, **form_kwargs)
        return factory.build_formset()

def build_form(schema, **kwargs):
    """Build a single form."""
    return VoucherFormFactory(schema, **kwargs).build_form()

def build_formset(schema, **kwargs):
    """Build a formset."""
    return VoucherFormFactory(schema, **kwargs).build_formset()


def get_voucher_ui_header(organization, journal_type=None):
    """Return the header portion of a VoucherModeConfig schema if it exists."""
    try:
        from accounting.models import VoucherModeConfig
        cfg = None
        if organization and journal_type:
            cfg = VoucherModeConfig.objects.filter(
                organization=organization,
                journal_type__code=journal_type,
                is_active=True,
            ).first()
        if not cfg and organization:
            cfg = VoucherModeConfig.objects.filter(
                organization=organization,
                is_default=True,
                is_active=True,
            ).first()
        if cfg:
            ui = cfg.resolve_ui()
            return ui.get('header') if isinstance(ui, dict) else None
    except Exception:
        pass
    return None

from django.utils.functional import LazyObject

# Backward-compatible alias
FormBuilder = VoucherFormFactory

class LazyVoucherForms(LazyObject):
    def _setup(self):
        from .models import VoucherModeConfig
        self._wrapped = {
            config.code: FormBuilder(config.resolve_ui_schema()).build_form()
            for config in VoucherModeConfig.objects.all()
        }

VOUCHER_FORMS = LazyVoucherForms()

def build_form(schema, **kwargs):
    """Build a single form."""
    return VoucherFormFactory(schema, **kwargs).build_form()

def build_formset(schema, **kwargs):
    """Build a formset."""
    return VoucherFormFactory(schema, **kwargs).build_formset()
