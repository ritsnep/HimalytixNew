from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from usermanagement.models import Organization
from accounting.utils.audit import log_audit_event

from .models import ConfigurationEntry, FeatureToggle


def _org_cache_key(org: Optional[Organization]) -> str:
    return f"org:{org.pk}" if org else "org:global"


@dataclass
class ConfigurationValue:
    scope: str
    key: str
    value: Any
    organization_id: Optional[int]
    source: str  # "org" or "global"


class ConfigurationService:
    CACHE_TTL_SECONDS = 300

    @classmethod
    def _entry_cache_key(cls, *, org: Optional[Organization], scope: str, key: str) -> str:
        return f"config:{_org_cache_key(org)}:{scope}:{key}"

    @classmethod
    def get_value(cls, *, organization: Optional[Organization], scope: str, key: str, default: Any = None) -> Any:
        """Fetch configuration value honoring org-specific override then global fallback."""
        org = organization
        cache_key_org = cls._entry_cache_key(org=org, scope=scope, key=key)
        cached = cache.get(cache_key_org)
        if cached is not None:
            return cached

        query = Q(scope=scope, key=key)
        if org:
            query &= (Q(organization=org) | Q(organization__isnull=True))
        else:
            query &= Q(organization__isnull=True)

        entry = (
            ConfigurationEntry.objects.filter(query)
            .order_by("organization_id")
            .first()
        )
        if entry is None:
            return default

        value = entry.value
        cache_key = cls._entry_cache_key(org=entry.organization, scope=scope, key=key)
        cache.set(cache_key, value, cls.CACHE_TTL_SECONDS)
        if entry.organization:
            cache.set(cache_key_org, value, cls.CACHE_TTL_SECONDS)
        return value

    @classmethod
    def set_value(
        cls,
        *,
        organization: Optional[Organization],
        scope: str,
        key: str,
        value: Any,
        user=None,
        description: Optional[str] = None,
        is_sensitive: bool = False,
    ) -> ConfigurationEntry:
        with transaction.atomic():
            entry, _ = ConfigurationEntry.objects.select_for_update().get_or_create(
                organization=organization,
                scope=scope,
                key=key,
                defaults={"value": value, "description": description or "", "is_sensitive": is_sensitive},
            )
            previous_state = {"value": entry.value, "description": entry.description, "is_sensitive": entry.is_sensitive}
            entry.value = value
            if description is not None:
                entry.description = description
            entry.is_sensitive = is_sensitive
            if user:
                entry.updated_by = user
            entry.save()

        cache.delete(cls._entry_cache_key(org=organization, scope=scope, key=key))
        log_audit_event(
            user,
            entry,
            "update",
            before_state=previous_state,
            after_state={"value": entry.value, "description": entry.description, "is_sensitive": entry.is_sensitive},
            organization=organization,
        )
        return entry


class FeatureToggleService:
    CACHE_TTL_SECONDS = 120

    @classmethod
    def _toggle_cache_key(cls, *, org: Optional[Organization], module: str, key: str) -> str:
        return f"feature:{_org_cache_key(org)}:{module}:{key}"

    @classmethod
    def is_enabled(cls, *, organization: Optional[Organization], module: str, key: str, default: bool = False) -> bool:
        cache_key = cls._toggle_cache_key(org=organization, module=module, key=key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        query = Q(module=module, key=key)
        if organization:
            query &= (Q(organization=organization) | Q(organization__isnull=True))
        else:
            query &= Q(organization__isnull=True)

        toggle = (
            FeatureToggle.objects.filter(query)
            .order_by("organization_id")
            .first()
        )
        enabled = toggle.is_active() if toggle else default
        cache.set(cache_key, enabled, cls.CACHE_TTL_SECONDS)
        return enabled

    @classmethod
    def set_toggle(
        cls,
        *,
        organization: Optional[Organization],
        module: str,
        key: str,
        is_enabled: bool,
        user=None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        starts_on=None,
        expires_on=None,
    ) -> FeatureToggle:
        with transaction.atomic():
            toggle, _ = FeatureToggle.objects.select_for_update().get_or_create(
                organization=organization,
                module=module,
                key=key,
                defaults={"is_enabled": is_enabled},
            )
            previous_state = {
                "is_enabled": toggle.is_enabled,
                "description": toggle.description,
                "metadata": toggle.metadata,
                "starts_on": toggle.starts_on,
                "expires_on": toggle.expires_on,
            }
            toggle.is_enabled = is_enabled
            if description is not None:
                toggle.description = description
            if metadata is not None:
                toggle.metadata = metadata
            toggle.starts_on = starts_on
            toggle.expires_on = expires_on
            if user:
                toggle.updated_by = user
            toggle.save()
        cache.delete(cls._toggle_cache_key(org=organization, module=module, key=key))
        log_audit_event(
            user,
            toggle,
            "update",
            before_state=previous_state,
            after_state={
                "is_enabled": toggle.is_enabled,
                "description": toggle.description,
                "metadata": toggle.metadata,
                "starts_on": toggle.starts_on,
                "expires_on": toggle.expires_on,
            },
            organization=organization,
        )
        return toggle
