import json
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any

from django.conf import settings


SUPPORTED_FIELD_TYPES = {
    "char",
    "text",
    "textarea",
    "number",
    "date",
    "datetime",
    "decimal",
    "integer",
    "boolean",
    "checkbox",
    "select",
    "account",
    "party",
    "customer",
    "vendor",
    "product",
    "warehouse",
    "cost_center",
    "department",
    "project",
    "journal_type",
    "period",
    "currency",
    "rate",
    "tax_code",
    "uom",
    "lookup",
    "typeahead",
    "autocomplete",
    "bsdate",
}


def _default_schema_path() -> Path:
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base_dir / "accounting" / "schemas" / "voucher_ui_schema.json"


def _load_json_schema(schema_path: Path) -> Dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_section_fields(section: Any) -> Iterable[Tuple[str, Dict[str, Any]]]:
    if section is None:
        return

    if isinstance(section, dict) and "fields" in section:
        section = section.get("fields")

    if isinstance(section, dict):
        for name, field_def in section.items():
            if name == "__order__":
                continue
            if isinstance(field_def, dict):
                yield name, field_def
    elif isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                name = item.get("name") or ""
                yield name, item


def _collect_fields(ui_schema: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    if not isinstance(ui_schema, dict):
        return []

    schema_root = ui_schema
    if isinstance(schema_root.get("sections"), dict):
        schema_root = schema_root["sections"]

    for section_key in ("header", "lines"):
        section = schema_root.get(section_key)
        if section is None:
            continue
        for name, field_def in _iter_section_fields(section):
            yield name, field_def


def validate_ui_schema(
    ui_schema: Dict[str, Any],
    schema_path: Path | None = None,
    *,
    strict_types: bool = True,
) -> List[str]:
    errors: List[str] = []
    schema_path = schema_path or _default_schema_path()

    try:
        import jsonschema
    except Exception as exc:  # pragma: no cover - dependency missing
        errors.append(f"jsonschema not available: {exc}")
        return errors

    try:
        schema = _load_json_schema(schema_path)
    except Exception as exc:
        errors.append(f"Failed to load JSON schema: {exc}")
        return errors

    try:
        jsonschema.validate(instance=ui_schema or {}, schema=schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"Schema validation error: {exc.message}")

    # Additional semantic checks
    for name, field_def in _collect_fields(ui_schema or {}):
        field_type = (field_def or {}).get("type")
        if not field_type:
            errors.append(f"Field '{name or '<missing name>'}' missing required 'type'.")
            continue
        if strict_types and field_type not in SUPPORTED_FIELD_TYPES:
            errors.append(f"Field '{name or '<missing name>'}' uses unsupported type '{field_type}'.")
        if field_type in ("number", "decimal", "integer"):
            step_val = (field_def or {}).get("step")
            if step_val is None:
                errors.append(
                    f"Field '{name or '<missing name>'}' missing required 'step' for numeric type '{field_type}'."
                )
        if field_type == "select":
            choices = (field_def or {}).get("choices")
            if choices in (None, "", []):
                errors.append(f"Field '{name or '<missing name>'}' missing required 'choices' for select.")

    return errors
