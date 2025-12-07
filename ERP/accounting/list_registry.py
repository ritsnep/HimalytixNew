"""Smart list registry and inference for dynamic filters and bulk actions."""
from __future__ import annotations

from typing import Dict, List, Optional, Set, TypedDict

from django.db import models


class ListConfig(TypedDict, total=False):
    search_fields: List[str]
    choice_fields: List[str]
    boolean_fields: List[str]
    currency_field: Optional[str]
    date_range_fields: List[str]
    bulk_actions: List[str]
    order_by: List[str]


# Explicit overrides per model name (lowercase model_name)
REGISTRY: Dict[str, ListConfig] = {
    "vendor": {
        "search_fields": [
            "code",
            "display_name",
            "legal_name",
            "email",
            "phone_number",
            "tax_id",
        ],
        "choice_fields": ["status"],
        "boolean_fields": ["on_hold", "is_active"],
        "currency_field": "default_currency",
        "bulk_actions": ["activate", "deactivate", "hold", "unhold"],
        "order_by": ["display_name"],
    },
    "customer": {
        "search_fields": ["code", "display_name", "legal_name", "email", "phone_number"],
        "choice_fields": ["status"],
        "boolean_fields": ["on_hold", "is_active"],
        "currency_field": "default_currency",
        "bulk_actions": ["activate", "deactivate", "hold", "unhold"],
        "order_by": ["display_name"],
    },
    "costcenter": {
        "search_fields": ["code", "name", "description"],
        "choice_fields": [],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "department": {
        "search_fields": ["code", "name"],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "project": {
        "search_fields": ["code", "name", "description"],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "fiscalyear": {
        "search_fields": ["code", "name"],
        "choice_fields": ["status"],
        "boolean_fields": ["is_current", "is_default"],
        "bulk_actions": [],
        "order_by": ["-start_date"],
    },
    "accountingperiod": {
        "search_fields": ["name", "period_number"],
        "choice_fields": ["status"],
        "boolean_fields": ["is_current"],
        "bulk_actions": [],
        "order_by": ["period_number"],
    },
    "accounttype": {
        "search_fields": ["code", "name", "classification"],
        "choice_fields": ["nature"],
        "boolean_fields": ["is_archived", "system_type"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "currency": {
        "search_fields": ["currency_code", "currency_name", "symbol"],
        "choice_fields": ["status"] if False else [],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["currency_code"],
    },
    "currencyexchangerate": {
        "search_fields": ["from_currency__currency_code", "to_currency__currency_code"],
        "choice_fields": [],
        "boolean_fields": [],
        "bulk_actions": [],
        "order_by": ["-rate_date"],
    },
    "taxauthority": {
        "search_fields": ["code", "name"],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "taxtype": {
        "search_fields": ["code", "name"],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "taxcode": {
        "search_fields": ["code", "name"],
        "choice_fields": ["status"],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
        "order_by": ["code"],
    },
    "voucherudfconfig": {
        "search_fields": ["name"],
        "boolean_fields": ["is_active"],
        "bulk_actions": ["activate", "deactivate"],
    },
    "vouchermodeconfig": {
        "search_fields": ["name", "description"],
        "choice_fields": ["journal_type"],
        "boolean_fields": ["is_active", "is_default"],
        "bulk_actions": ["activate", "deactivate"],
    },
}


DEFAULTS: ListConfig = {
    "search_fields": [],
    "choice_fields": [],
    "boolean_fields": [],
    "currency_field": None,
    "date_range_fields": ["created_at", "updated_at"],
    "bulk_actions": [],
    "order_by": [],
}


def _field_names(model: models.Model, field_type) -> List[str]:
    return [f.name for f in model._meta.get_fields() if isinstance(f, field_type)]


def _has_field(model: models.Model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _infer_search_fields(model: models.Model) -> List[str]:
    text_fields = (models.CharField, models.TextField, models.EmailField, models.URLField)
    candidates: List[str] = []
    for f in model._meta.get_fields():
        if isinstance(f, text_fields) and not f.is_relation:
            candidates.append(f.name)
        if len(candidates) >= 4:
            break
    return candidates


def _infer_choice_fields(model: models.Model) -> List[str]:
    fields: List[str] = []
    for f in model._meta.get_fields():
        if getattr(f, "choices", None):
            fields.append(f.name)
    return fields


def _infer_boolean_fields(model: models.Model) -> List[str]:
    return _field_names(model, models.BooleanField)


def _infer_currency_field(model: models.Model) -> Optional[str]:
    for f in model._meta.get_fields():
        if f.is_relation and getattr(f, "related_model", None):
            if f.related_model.__name__.lower() == "currency":
                return f.name
    return None


def _infer_bulk_actions(model: models.Model, cfg: ListConfig) -> List[str]:
    actions: Set[str] = set(cfg.get("bulk_actions", []))
    has_is_active = _has_field(model, "is_active")
    has_status = _has_field(model, "status")
    has_on_hold = _has_field(model, "on_hold")
    if has_is_active or has_status:
        actions.update(["activate", "deactivate"])
    if has_on_hold:
        actions.update(["hold", "unhold"])
    return sorted(actions)


def get_config(model: models.Model) -> ListConfig:
    model_key = model._meta.model_name.lower()
    base = dict(DEFAULTS)
    override = REGISTRY.get(model_key, {})

    # Infer from model structure
    base["search_fields"] = override.get("search_fields") or _infer_search_fields(model)
    base["choice_fields"] = override.get("choice_fields") or _infer_choice_fields(model)
    base["boolean_fields"] = override.get("boolean_fields") or _infer_boolean_fields(model)
    base["currency_field"] = override.get("currency_field") or _infer_currency_field(model)
    base["date_range_fields"] = override.get("date_range_fields") or DEFAULTS["date_range_fields"]
    base["order_by"] = override.get("order_by") or []

    base["bulk_actions"] = _infer_bulk_actions(model, override)

    # Ensure uniqueness
    for key in ["search_fields", "choice_fields", "boolean_fields", "date_range_fields", "order_by", "bulk_actions"]:
        base[key] = list(dict.fromkeys(base.get(key, [])))

    return base
