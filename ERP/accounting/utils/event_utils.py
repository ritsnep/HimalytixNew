from __future__ import annotations

from accounting.models import IntegrationEvent


def emit_integration_event(event_type: str, source_object: object, payload: dict | None = None) -> IntegrationEvent:
    payload = payload or {}
    event = IntegrationEvent.objects.create(
        event_type=event_type,
        payload=payload,
        source_object=source_object.__class__.__name__,
        source_id=str(getattr(source_object, 'pk', '')),
    )
    return event
