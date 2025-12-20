from __future__ import annotations

from typing import Any, Dict, List


def _field_to_ui(field: Dict[str, Any], order_no: int) -> Dict[str, Any]:
    field_type = field.get("field_type") or field.get("type") or "char"
    ui: Dict[str, Any] = {
        "type": field_type,
        "label": field.get("label") or field.get("name"),
        "required": field.get("required", False),
        "help_text": field.get("help_text"),
        "order_no": order_no,
    }

    validators = field.get("validators") or {}
    if "min" in validators:
        ui["min_value"] = validators.get("min")
    if "max" in validators:
        ui["max_value"] = validators.get("max")
    if "regex" in validators:
        ui["pattern"] = validators.get("regex")

    default = field.get("default")
    if default is not None:
        ui["default"] = default

    ui_meta = field.get("ui") or {}
    if field.get("placeholder"):
        ui["placeholder"] = field.get("placeholder")
    elif ui_meta.get("placeholder"):
        ui["placeholder"] = ui_meta.get("placeholder")
    if ui_meta.get("autofocus"):
        ui["autofocus"] = True
    if ui_meta.get("hidden"):
        ui["hidden"] = True
    if ui_meta.get("disabled"):
        ui["disabled"] = True
    if ui_meta.get("read_only"):
        ui["read_only"] = True

    step_val = ui_meta.get("step") or validators.get("step")
    if step_val is not None:
        ui["step"] = step_val

    choices = field.get("choices")
    if choices is not None:
        ui["choices"] = choices

    lookup = field.get("lookup") or {}
    if lookup:
        if lookup.get("model"):
            ui["lookup_model"] = lookup.get("model")
        if lookup.get("url"):
            ui["lookup_url"] = lookup.get("url")
        if lookup.get("kind"):
            ui["lookup_kind"] = lookup.get("kind")

    attrs = ui_meta.get("attrs")
    if attrs:
        ui.setdefault("kwargs", {}).setdefault("widget", {}).setdefault("attrs", {}).update(attrs)

    return ui


def definition_to_ui_schema(definition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert normalized voucher schema into legacy UI schema structure.
    """
    definition = definition or {}
    header_fields = definition.get("header_fields") or definition.get("header") or []
    line_fields = definition.get("line_fields") or definition.get("lines") or []

    def _convert(fields: List[Dict[str, Any]]) -> tuple[Dict[str, Any], List[str]]:
        result: Dict[str, Any] = {}
        order: List[str] = []
        has_order = any(field.get("order_no") is not None for field in fields if isinstance(field, dict))
        if has_order:
            try:
                fields = sorted(
                    fields,
                    key=lambda f: f.get("order_no") if isinstance(f, dict) and f.get("order_no") is not None else 9999,
                )
            except Exception:
                pass
        for idx, field in enumerate(fields, 1):
            key = field.get("key") or field.get("name")
            if not key:
                continue
            result[key] = _field_to_ui(field, idx)
            order.append(key)
        return result, order

    header_dict, header_order = _convert(header_fields)
    lines_dict, lines_order = _convert(line_fields)
    if header_order:
        header_dict["__order__"] = header_order
    if lines_order:
        lines_dict["__order__"] = lines_order
    schema: Dict[str, Any] = {
        "header": header_dict,
        "lines": lines_dict,
    }
    settings = definition.get("settings")
    if isinstance(settings, dict):
        schema["settings"] = settings
    return schema


def ui_schema_to_definition(ui_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert legacy UI schema into normalized voucher schema format.
    """
    ui_schema = ui_schema or {}
    sections = ui_schema.get("sections") if isinstance(ui_schema.get("sections"), dict) else ui_schema
    if not isinstance(sections, dict):
        return {"header_fields": [], "line_fields": []}

    def _collect(section):
        fields = []
        if isinstance(section, dict):
            order = section.get("__order__") or [k for k in section.keys() if k != "__order__"]
            for name in order:
                cfg = section.get(name)
                if not isinstance(cfg, dict):
                    cfg = {"type": "char", "label": str(cfg)}
                fields.append((name, cfg))
        elif isinstance(section, list):
            for item in section:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("field")
                    if name:
                        fields.append((name, item))
        return fields

    def _convert(items):
        result = []
        for name, cfg in items:
            if not name:
                continue
            field = {
                "key": name,
                "label": cfg.get("label"),
                "field_type": cfg.get("type") or "char",
                "required": cfg.get("required", False),
                "default": cfg.get("default"),
            }
            validators = {}
            if cfg.get("min_value") is not None:
                validators["min"] = cfg.get("min_value")
            if cfg.get("max_value") is not None:
                validators["max"] = cfg.get("max_value")
            if cfg.get("pattern"):
                validators["regex"] = cfg.get("pattern")
            if cfg.get("step") is not None:
                validators["step"] = cfg.get("step")
            if validators:
                field["validators"] = validators

            ui_meta = {}
            for key in ("placeholder", "hidden", "disabled", "read_only", "autofocus"):
                if cfg.get(key) is not None:
                    ui_meta[key] = cfg.get(key)
            kwargs = cfg.get("kwargs") or {}
            attrs = kwargs.get("widget", {}).get("attrs") if isinstance(kwargs, dict) else None
            if attrs:
                ui_meta["attrs"] = attrs
            if ui_meta:
                field["ui"] = ui_meta

            if cfg.get("choices") is not None:
                field["choices"] = cfg.get("choices")
            lookup = {}
            if cfg.get("lookup_model"):
                lookup["model"] = cfg.get("lookup_model")
            if cfg.get("lookup_url"):
                lookup["url"] = cfg.get("lookup_url")
            if cfg.get("lookup_kind"):
                lookup["kind"] = cfg.get("lookup_kind")
            if lookup:
                field["lookup"] = lookup

            result.append(field)
        return result

    header_items = _collect(sections.get("header"))
    line_items = _collect(sections.get("lines"))

    return {
        "header_fields": _convert(header_items),
        "line_fields": _convert(line_items),
    }
