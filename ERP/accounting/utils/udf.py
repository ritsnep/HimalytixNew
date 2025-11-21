from __future__ import annotations

from typing import Dict, Any

from django.contrib.contenttypes.models import ContentType

from accounting.models import UDFDefinition, UDFValue


def save_udf_values(instance, udf_data: Dict[str, Any]) -> None:
    """
    Persist UDF values for a given model instance.

    Unknown field names are ignored to keep this helper tolerant.
    """
    content_type = ContentType.objects.get_for_model(instance)
    for field_name, value in udf_data.items():
        try:
            udf_def = UDFDefinition.objects.get(
                organization=getattr(instance, "organization", None),
                content_type=content_type,
                field_name=field_name,
            )
        except UDFDefinition.DoesNotExist:
            continue

        UDFValue.objects.update_or_create(
            udf_definition=udf_def,
            content_type=content_type,
            object_id=instance.pk,
            defaults={"value": value},
        )
