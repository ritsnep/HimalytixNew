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


PAPER_SIZES = [
    ("A4", "A4"),
    ("A5", "A5"),
]

DEFAULT_OPTIONS: Dict[str, Any] = {
    "paper_size": "A4",
}


def normalize_paper_size(value: str | None) -> str:
    if value in {"A4", "A5"}:
        return value  # type: ignore[return-value]
    return "A4"


def normalize_template_name(value: str | None) -> str:
    if value in ALLOWED_TEMPLATES:
        return value  # type: ignore[return-value]
    return DEFAULT_TEMPLATE


def get_user_print_config(user) -> Tuple[PrintTemplateConfig | None, Dict[str, Any]]:
    """Return (config_obj_or_none, merged_config_dict)."""

    if not getattr(user, "is_authenticated", False):
        default_data = {**DEFAULT_TOGGLES, **DEFAULT_OPTIONS, "template_name": DEFAULT_TEMPLATE}
        return None, default_data

    try:
        config_obj = PrintTemplateConfig.objects.get(user=user)
    except PrintTemplateConfig.DoesNotExist:
        default_data = {**DEFAULT_TOGGLES, **DEFAULT_OPTIONS, "template_name": DEFAULT_TEMPLATE}
        return None, default_data

    config_data: Dict[str, Any] = {**DEFAULT_TOGGLES, **DEFAULT_OPTIONS, **(config_obj.config or {})}
    config_data["template_name"] = normalize_template_name(config_obj.template_name)
    config_data["paper_size"] = normalize_paper_size(config_data.get("paper_size"))
    return config_obj, config_data


def save_user_print_config(user, template_name: str, config_data: Dict[str, Any]) -> PrintTemplateConfig:
    """Create or update the PrintTemplateConfig for the given user."""

    config_obj, _ = get_user_print_config(user)
    if config_obj is None:
        config_obj = PrintTemplateConfig(user=user)

    config_obj.template_name = normalize_template_name(template_name)

    payload: Dict[str, Any] = {}
    for key in DEFAULT_TOGGLES.keys():
        payload[key] = bool(config_data.get(key, DEFAULT_TOGGLES[key]))
    payload["paper_size"] = normalize_paper_size(config_data.get("paper_size"))

    config_obj.config = payload
    config_obj.save()
    return config_obj


DOCUMENT_TYPE_MODELS = {
    'journal': ('accounting.Journal', 'journal'),
    'purchase_order': ('purchasing.PurchaseOrder', 'purchase_order'),
    'sales_order': ('accounting.SalesOrder', 'sales_order'),
    'sales_invoice': ('accounting.SalesInvoice', 'sales_invoice'),
}

def get_document_model(document_type):
    """Get the model class and template prefix for a document type."""
    if document_type not in DOCUMENT_TYPE_MODELS:
        raise ValueError(f"Unknown document type: {document_type}")
    app_label, model_name = DOCUMENT_TYPE_MODELS[document_type][0].split('.')
    from django.apps import apps
    model = apps.get_model(app_label, model_name)
    template_prefix = DOCUMENT_TYPE_MODELS[document_type][1]
    return model, template_prefix
