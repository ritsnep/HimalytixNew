from __future__ import annotations

from accounting.models import IntegrationEvent


def emit_integration_event(event_type: str, source_object: object, payload: dict | None = None) -> IntegrationEvent:
    payload = payload or {}
    organization_id = getattr(getattr(source_object, "organization", None), "id", None)
    if not organization_id:
        organization_id = getattr(source_object, "organization_id", None)
    if organization_id and "organization_id" not in payload:
        payload["organization_id"] = organization_id
    event = IntegrationEvent.objects.create(
        event_type=event_type,
        payload=payload,
        source_object=source_object.__class__.__name__,
        source_id=str(getattr(source_object, 'pk', '')),
    )
    return event
