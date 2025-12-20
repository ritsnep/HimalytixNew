from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from django.utils.module_loading import import_string

from configuration.models import ConfigurationEntry
from configuration.services import ConfigurationService

logger = logging.getLogger(__name__)


class HookRunner:
    """Loads and executes configured accounting hooks for an organization."""

    CONFIG_KEY = "accounting_hooks"

    def __init__(self, organization):
        self.organization = organization

    def _load_definitions(self) -> Iterable[dict]:
        hooks = ConfigurationService.get_value(
            organization=self.organization,
            scope=ConfigurationEntry.SCOPE_FINANCE,
            key=self.CONFIG_KEY,
            default=[],
        )
        if not isinstance(hooks, list):
            return []
        return hooks

    def run(
        self,
        event: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        raise_on_error: bool = False,
    ) -> None:
        payload = payload or {}
        hooks = [
            definition
            for definition in self._load_definitions()
            if definition.get("event") == event and definition.get("enabled", True)
        ]
        if not hooks:
            return

        context = {
            "event": event,
            "organization_id": getattr(self.organization, "pk", None),
            "payload": payload,
        }
        for definition in hooks:
            path = definition.get("path")
            if not path:
                continue
            try:
                callback = import_string(path)
            except Exception as exc:
                logger.exception("Unable to import hook %s: %s", path, exc)
                continue
            try:
                callback(context)
            except Exception as exc:
                logger.exception("Hook %s failed for event %s: %s", path, event, exc)
                if raise_on_error:
                    raise
