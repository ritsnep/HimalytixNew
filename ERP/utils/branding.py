"""Utility helpers for tenant/organization specific branding."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from django.templatetags.static import static

from tenancy.models import Tenant, TenantConfig

# Mapping of TenantConfig keys to dictionary keys exposed to templates/UI
BRANDING_KEY_MAP = {
    "branding.favicon_url": "favicon_url",
    "branding.logo_light_url": "logo_light_url",
    "branding.logo_dark_url": "logo_dark_url",
    "branding.logo_symbol_url": "logo_symbol_url",
    "branding.theme_color": "theme_color",
}


def _cast_config_value(value: Optional[str], data_type: Optional[str]) -> Any:
    """Best-effort conversion for stored TenantConfig values."""
    if value in (None, ""):
        return None
    kind = (data_type or "string").lower()
    if kind in {"json", "dict"}:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    if kind in {"int", "integer"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if kind in {"float", "decimal"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if kind in {"bool", "boolean"}:
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        return None
    return value


def _default_branding() -> Dict[str, Any]:
    """Base branding values used as a fallback when nothing is configured."""
    return {
        "favicon_url": static("images/favicon.ico"),
        "logo_light_url": static("images/himalytix-sm.svg"),
        "logo_dark_url": static("images/himalytix-sm.svg"),
        "logo_symbol_url": static("images/himalytix-sm.svg"),
        "theme_color": "#1c84ee",
    }


def get_branding_for_tenant(tenant: Optional[Tenant] = None) -> Dict[str, Any]:
    """Return merged branding data for a tenant with safe defaults."""
    branding = _default_branding()
    if tenant is None:
        return branding

    configs = TenantConfig.objects.filter(
        tenant=tenant,
        config_key__in=BRANDING_KEY_MAP.keys(),
    ).values("config_key", "config_value", "data_type")

    for config in configs:
        dict_key = BRANDING_KEY_MAP[config["config_key"]]
        parsed_value = _cast_config_value(config["config_value"], config.get("data_type"))
        if parsed_value:
            branding[dict_key] = parsed_value
    return branding


def get_branding_from_request(request) -> Dict[str, Any]:  # type: ignore[override]
    """Convenience helper that derives branding for a Django request."""
    tenant = getattr(request, "tenant", None)
    return get_branding_for_tenant(tenant)
