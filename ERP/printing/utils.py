from __future__ import annotations

from typing import Any, Dict, Tuple

from .models import PrintTemplateConfig


TEMPLATE_CHOICES = [
    ("classic", "Journal Voucher – Classic"),
    ("compact", "Journal Voucher – Compact (Dense)"),
]

ALLOWED_TEMPLATES = {key for key, _label in TEMPLATE_CHOICES}
DEFAULT_TEMPLATE = "classic"


DEFAULT_TOGGLES: Dict[str, bool] = {
    "show_description": True,
    "show_department": True,
    "show_project": True,
    "show_cost_center": True,
    "show_tax_column": True,
    "show_audit": True,
    "show_signatures": True,
    "show_imbalance": True,
}


def normalize_template_name(value: str | None) -> str:
    if value in ALLOWED_TEMPLATES:
        return value  # type: ignore[return-value]
    return DEFAULT_TEMPLATE


def get_user_print_config(user) -> Tuple[PrintTemplateConfig | None, Dict[str, Any]]:
    """Return (config_obj_or_none, merged_config_dict)."""

    if not getattr(user, "is_authenticated", False):
        default_data = {**DEFAULT_TOGGLES, "template_name": DEFAULT_TEMPLATE}
        return None, default_data

    try:
        config_obj = PrintTemplateConfig.objects.get(user=user)
    except PrintTemplateConfig.DoesNotExist:
        default_data = {**DEFAULT_TOGGLES, "template_name": DEFAULT_TEMPLATE}
        return None, default_data

    config_data: Dict[str, Any] = {**DEFAULT_TOGGLES, **(config_obj.config or {})}
    config_data["template_name"] = normalize_template_name(config_obj.template_name)
    return config_obj, config_data


def save_user_print_config(user, template_name: str, toggles_data: Dict[str, bool]) -> PrintTemplateConfig:
    """Create or update the PrintTemplateConfig for the given user."""

    config_obj, _ = get_user_print_config(user)
    if config_obj is None:
        config_obj = PrintTemplateConfig(user=user)

    config_obj.template_name = normalize_template_name(template_name)
    config_obj.config = toggles_data or {}
    config_obj.save()
    return config_obj
