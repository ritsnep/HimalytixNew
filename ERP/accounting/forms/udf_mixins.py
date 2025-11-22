from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from django import forms

from accounting.utils.udf import (
    get_udf_definitions_for_model,
    get_udf_values,
    save_udf_values,
)

if TYPE_CHECKING:  # pragma: no cover - hints only
    from accounting.models import UDFDefinition


class UDFFormMixin(forms.Form):
    """
    Injects dynamic UDF fields into forms and persists their values via the
    shared ``save_udf_values`` helper.
    """

    udf_field_prefix = "udf_"

    def __init__(self, *args, **kwargs):
        self._include_udf_fields = kwargs.pop("include_udf_fields", True)
        super().__init__(*args, **kwargs)
        self._udf_definitions: List[UDFDefinition] = []
        self._udf_field_map: Dict[str, str] = {}
        if self._include_udf_fields:
            self._init_udf_fields()

    # ------------------------------------------------------------------
    # Public helpers

    def get_cleaned_udf_data(self) -> Dict[str, Any]:
        if not getattr(self, "_udf_definitions", None) or not hasattr(self, "cleaned_data"):
            return {}

        payload: Dict[str, Any] = {}
        for definition in self._udf_definitions:
            field_name = self._udf_field_map.get(definition.field_name)
            if not field_name or field_name not in self.cleaned_data:
                continue
            value = self.cleaned_data[field_name]
            if self._should_skip_value(value, definition):
                continue
            payload[definition.field_name] = value
        return payload

    def save_udf_fields(self, instance=None) -> Dict[str, Any]:
        if not self._udf_definitions:
            return {}
        if instance is None:
            instance = getattr(self, "instance", None)
        if instance is None:
            return {}

        payload = self.get_cleaned_udf_data()
        if not payload:
            return {}

        if getattr(instance, "pk", None):
            save_udf_values(instance, payload, organization=self._organization_for_udf(instance))
            self.after_udf_save(instance, payload)
        return payload

    def after_udf_save(self, instance, payload: Dict[str, Any]) -> None:  # pragma: no cover - hook
        """Override in subclasses when additional side-effects are required."""

    def udf_payload_with_form_names(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mapped: Dict[str, Any] = {}
        for definition in self._udf_definitions:
            if definition.field_name in payload:
                mapped[self._udf_field_map.get(definition.field_name, definition.field_name)] = payload[
                    definition.field_name
                ]
        return mapped

    # ------------------------------------------------------------------
    # Internal helpers

    def _init_udf_fields(self) -> None:
        model = self._target_udf_model()
        organization = self._organization_for_udf()
        if not (model and organization):
            return

        self._udf_definitions = get_udf_definitions_for_model(model, organization)
        if not self._udf_definitions:
            return

        instance = getattr(self, "instance", None)
        initial_values: Dict[str, Any] = {}
        if instance and getattr(instance, "pk", None):
            initial_values = get_udf_values(instance, organization=organization)

        for definition in self._udf_definitions:
            field_name = self._form_field_name(definition.field_name)
            form_field = self._build_form_field(definition)
            self.fields[field_name] = form_field
            self._udf_field_map[definition.field_name] = field_name

            if initial_values and definition.field_name in initial_values:
                self.initial.setdefault(field_name, initial_values[definition.field_name])
            else:
                default_value = self._coerce_default(definition)
                if default_value is not None:
                    self.initial.setdefault(field_name, default_value)

    def _target_udf_model(self):
        if getattr(self, "udf_model", None):
            return self.udf_model
        if hasattr(self, "_meta") and getattr(self._meta, "model", None):
            return self._meta.model
        return None

    def _organization_for_udf(self, instance=None):
        if instance is not None and getattr(instance, "organization", None):
            return instance.organization
        if getattr(self, "organization", None):
            return self.organization
        instance = instance or getattr(self, "instance", None)
        return getattr(instance, "organization", None)

    def _form_field_name(self, field_name: str) -> str:
        if field_name.startswith(self.udf_field_prefix):
            return field_name
        return f"{self.udf_field_prefix}{field_name}"

    def _build_form_field(self, definition: "UDFDefinition") -> forms.Field:
        kwargs: Dict[str, Any] = {
            "label": definition.display_name,
            "required": definition.is_required,
            "help_text": definition.help_text or "",
        }
        field_type = (definition.field_type or "text").lower()

        if field_type == "number":
            field = forms.IntegerField(
                min_value=int(definition.min_value) if definition.min_value is not None else None,
                max_value=int(definition.max_value) if definition.max_value is not None else None,
                **kwargs,
            )
        elif field_type == "decimal":
            field = forms.DecimalField(
                max_digits=19,
                decimal_places=4,
                min_value=definition.min_value,
                max_value=definition.max_value,
                **kwargs,
            )
        elif field_type == "date":
            field = forms.DateField(**kwargs)
        elif field_type == "datetime":
            field = forms.DateTimeField(**kwargs)
        elif field_type == "boolean":
            kwargs["required"] = False
            field = forms.BooleanField(**kwargs)
        elif field_type == "select":
            field = forms.ChoiceField(
                choices=self._coerce_choices(definition),
                **kwargs,
            )
        elif field_type == "multiselect":
            field = forms.MultipleChoiceField(
                choices=self._coerce_choices(definition),
                **kwargs,
            )
        elif field_type == "json":
            field = forms.JSONField(**kwargs)
        else:
            field = forms.CharField(
                max_length=definition.max_length or 255,
                min_length=definition.min_length,
                **kwargs,
            )

        self._apply_widget_attrs(field, definition)
        return field

    def _coerce_choices(self, definition: "UDFDefinition") -> List[Tuple[Any, Any]]:
        choices = definition.choices or []
        coerced: List[Tuple[Any, Any]] = []
        if isinstance(choices, dict):
            return list(choices.items())
        for entry in choices:
            if isinstance(entry, dict):
                value = (
                    entry.get("value")
                    or entry.get("id")
                    or entry.get("code")
                    or entry.get("key")
                    or entry.get("label")
                )
                label = entry.get("label") or entry.get("name") or str(value)
            else:
                value = entry
                label = str(entry)
            if value is None:
                continue
            coerced.append((value, label))
        return coerced

    def _apply_widget_attrs(self, field: forms.Field, definition: "UDFDefinition") -> None:
        getter = getattr(definition, "get_field_widget_attrs", None)
        attrs = getter() if callable(getter) else {}
        if attrs:
            field.widget.attrs.update(attrs)

    def _coerce_default(self, definition: "UDFDefinition") -> Optional[Any]:
        default = definition.default_value
        if default in (None, ""):
            return None
        field_type = (definition.field_type or "text").lower()
        try:
            if field_type == "number":
                return int(default)
            if field_type == "decimal":
                return float(default)
            if field_type in {"multiselect", "json"}:
                return json.loads(default)
            if field_type == "boolean":
                return str(default).lower() in {"1", "true", "yes", "on"}
            if field_type == "date" or field_type == "datetime":
                # Let Django's Field handle coercion during validation.
                return default
        except (ValueError, TypeError, json.JSONDecodeError):
            return default
        return default

    @staticmethod
    def _should_skip_value(value: Any, definition: "UDFDefinition") -> bool:
        if value is None:
            return True
        if value == "":
            return True
        if isinstance(value, (list, tuple, dict)) and not value:
            return True
        return False