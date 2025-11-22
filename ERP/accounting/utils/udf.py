from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib.contenttypes.models import ContentType

from accounting.models import UDFDefinition, UDFValue


def _normalize_value_for_storage(value: Any) -> Any:
    """Ensure value is JSON serialisable before persisting."""

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, set):
        return list(value)
    return value


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, tuple, set, dict)) and not value:
        return True
    return False


def save_udf_values(instance, udf_data: Dict[str, Any], *, organization=None) -> None:
    """
    Persist UDF values for a given model instance.

    Unknown field names are ignored to keep this helper tolerant.
    """
    if instance is None:
        return

    organization = organization or getattr(instance, "organization", None)
    if organization is None:
        return

    content_type = ContentType.objects.get_for_model(instance)
    for field_name, value in udf_data.items():
        try:
            udf_def = UDFDefinition.objects.get(
                organization=organization,
                content_type=content_type,
                field_name=field_name,
            )
        except UDFDefinition.DoesNotExist:
            continue

        normalized = _normalize_value_for_storage(value)
        if _is_empty_value(normalized):
            UDFValue.objects.filter(
                udf_definition=udf_def,
                content_type=content_type,
                object_id=instance.pk,
            ).delete()
            continue

        UDFValue.objects.update_or_create(
            udf_definition=udf_def,
            content_type=content_type,
            object_id=instance.pk,
            defaults={"value": normalized},
        )


def get_udf_values(instance, *, organization=None) -> Dict[str, Any]:
    """Fetch all persisted UDF values for the instance."""

    if instance is None or not getattr(instance, "pk", None):
        return {}

    organization = organization or getattr(instance, "organization", None)
    if organization is None:
        return {}

    content_type = ContentType.objects.get_for_model(instance)
    qs = (
        UDFValue.objects.filter(
            content_type=content_type,
            object_id=instance.pk,
            udf_definition__organization=organization,
        )
        .select_related("udf_definition")
        .order_by("udf_definition__display_name")
    )
    return {value.udf_definition.field_name: value.value for value in qs}


def get_udf_definitions_for_model(model_or_instance, organization, *, include_inactive: bool = False) -> List[UDFDefinition]:
    """Return ordered UDF definitions scoped to a model/content type."""

    if not organization or model_or_instance is None:
        return []
    model = model_or_instance if isinstance(model_or_instance, type) else model_or_instance.__class__
    content_type = ContentType.objects.get_for_model(model)
    qs = UDFDefinition.objects.filter(
        organization=organization,
        content_type=content_type,
    )
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return list(qs.order_by("display_name", "field_name"))


def filterable_udfs(model_or_instance, organization) -> List[UDFDefinition]:
    return [udf for udf in get_udf_definitions_for_model(model_or_instance, organization) if udf.is_filterable]


def pivot_udfs(model_or_instance, organization) -> List[UDFDefinition]:
    return [udf for udf in get_udf_definitions_for_model(model_or_instance, organization) if udf.is_pivot_dim]


def serialize_udf_definition(udf: UDFDefinition) -> Dict[str, Any]:
    return {
        "id": udf.field_name,
        "label": udf.display_name,
        "type": udf.field_type,
        "required": udf.is_required,
        "isFilterable": udf.is_filterable,
        "isPivotDim": udf.is_pivot_dim,
        "helpText": udf.help_text or "",
        "choices": udf.choices or [],
        "default": udf.default_value,
    }
