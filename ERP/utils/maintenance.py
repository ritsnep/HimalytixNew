"""
Maintenance mode utilities.
Centralizes state storage (cache/Redis), snapshots of in-flight requests,
and helpers used by middleware, management commands, and templates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


STATE_CACHE_KEY = "maintenance:state"
SNAPSHOT_CACHE_KEY = "maintenance:snapshot:{key}"


@dataclass
class MaintenanceState:
    enabled: bool
    message: str
    status_text: str
    app_version: str
    updated_at: str
    retry_after: int


def get_effective_app_version() -> str:
    """
    Resolve the current app version, preferring the cached maintenance state
    (which can be bumped without a deploy) and falling back to settings.
    """
    state = cache.get(STATE_CACHE_KEY) or {}
    return state.get("app_version") or getattr(settings, "APP_VERSION", "dev")


def default_state() -> Dict[str, Any]:
    """Default maintenance state derived from environment/settings."""
    return {
        "enabled": getattr(settings, "MAINTENANCE_MODE", False),
        "message": getattr(
            settings,
            "MAINTENANCE_MESSAGE",
            "Scheduled maintenance is in progress. Please try again shortly.",
        ),
        "status_text": getattr(settings, "MAINTENANCE_STATUS_TEXT", ""),
        "app_version": get_effective_app_version(),
        "retry_after": getattr(settings, "MAINTENANCE_RETRY_AFTER", 300),
        "updated_at": timezone.now().isoformat(),
    }


def get_maintenance_state() -> Dict[str, Any]:
    """Return the persisted maintenance state (cache/Redis backed)."""
    state = cache.get(STATE_CACHE_KEY)
    if state is None:
        state = default_state()
        cache.set(STATE_CACHE_KEY, state, None)
    return state


def set_maintenance_state(
    enabled: bool,
    message: Optional[str] = None,
    status_text: Optional[str] = None,
    app_version: Optional[str] = None,
    retry_after: Optional[int] = None,
) -> Dict[str, Any]:
    """Persist maintenance state and return the updated payload."""
    state = get_maintenance_state()
    state.update(
        {
            "enabled": enabled,
            "message": message or state.get("message"),
            "status_text": status_text if status_text is not None else state.get("status_text", ""),
            "app_version": app_version or state.get("app_version") or get_effective_app_version(),
            "retry_after": retry_after or state.get("retry_after") or getattr(settings, "MAINTENANCE_RETRY_AFTER", 300),
            "updated_at": timezone.now().isoformat(),
        }
    )
    cache.set(STATE_CACHE_KEY, state, None)
    return state


def _resolve_identity(request, create: bool = False) -> Optional[str]:
    """
    Build a stable identity key for the request (user > session > none).
    Ensures the session exists so anonymous users still get a resume token.
    """
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        return f"user:{request.user.pk}"

    if getattr(request, "session", None) is None:
        return None

    session_key = request.session.session_key
    if session_key is None and create:
        request.session.save()
        session_key = request.session.session_key

    return f"session:{session_key}" if session_key else None


def _extract_payload(request) -> Optional[Any]:
    """
    Capture a lightweight representation of the request payload.
    Avoids file uploads and truncates large bodies to keep Redis lean.
    """
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    content_type = (request.META.get("CONTENT_TYPE") or "").lower()
    max_bytes = getattr(settings, "MAINTENANCE_CAPTURE_MAX_BYTES", 4096)

    if "multipart/form-data" in content_type:
        return {"note": "multipart payload skipped"}

    raw_body = request.body or b""
    trimmed = raw_body[:max_bytes]
    text_body = trimmed.decode(request.encoding or "utf-8", errors="ignore")

    if "application/json" in content_type:
        try:
            parsed = json.loads(text_body) if text_body else {}
        except Exception:
            parsed = text_body
        if len(raw_body) > max_bytes:
            return {"truncated": True, "preview": parsed}
        return parsed

    data = request.POST.dict()
    if not data and text_body:
        preview = text_body
        if len(raw_body) > max_bytes:
            preview = f"{text_body}...<truncated>"
        data = {"body": preview}

    return data or None


def capture_request_snapshot(request) -> Optional[Dict[str, Any]]:
    """
    Persist a snapshot of the in-flight request so we can resume the user
    when maintenance ends.
    """
    identity = _resolve_identity(request, create=True)
    if not identity:
        return None

    payload = _extract_payload(request)
    snapshot = {
        "identity": identity,
        "path": request.path,
        "method": request.method,
        "query_string": request.META.get("QUERY_STRING", ""),
        "payload": payload,
        "app_version": get_effective_app_version(),
        "captured_at": timezone.now().isoformat(),
    }

    cache.set(
        SNAPSHOT_CACHE_KEY.format(key=identity),
        snapshot,
        getattr(settings, "MAINTENANCE_SNAPSHOT_TTL", 60 * 60 * 6),
    )
    return snapshot


def pop_snapshot_for_request(request) -> Optional[Dict[str, Any]]:
    """
    Fetch and delete the cached snapshot for the current user/session.
    Used after maintenance ends to surface a resume hint to the UI.
    """
    identity = _resolve_identity(request, create=False)
    if not identity:
        return None

    cache_key = SNAPSHOT_CACHE_KEY.format(key=identity)
    snapshot = cache.get(cache_key)
    if snapshot:
        cache.delete(cache_key)
    return snapshot


def should_bypass_maintenance(request) -> bool:
    """
    Decide whether the current request should skip maintenance mode.
    - Health/static/media/status endpoints
    - Explicit allowlist in settings
    - Superusers/whitelisted IPs when enabled
    """
    path = request.path or ""
    allow_urls = getattr(
        settings,
        "MAINTENANCE_ALLOW_URLS",
        ["/health/", "/health/ready/", "/health/live/", "/metrics", "/maintenance/status/", "/maintenance/stream/"],
    )
    for url in allow_urls:
        if path.startswith(url):
            return True

    static_url = getattr(settings, "STATIC_URL", "")
    if static_url:
        normalized_static = static_url if static_url.startswith("/") else f"/{static_url}"
        if path.startswith(normalized_static):
            return True

    media_url = getattr(settings, "MEDIA_URL", "")
    if media_url:
        normalized_media = media_url if media_url.startswith("/") else f"/{media_url}"
        if path.startswith(normalized_media):
            return True

    if getattr(settings, "MAINTENANCE_ALLOW_SUPERUSER", True):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.is_superuser:
            return True

    allowed_ips = getattr(settings, "MAINTENANCE_ALLOW_IPS", [])
    if allowed_ips:
        ip = request.META.get("REMOTE_ADDR")
        if ip in allowed_ips:
            return True

    return False


def serialize_state() -> Dict[str, Any]:
    """Expose maintenance state in a JSON-safe form."""
    state = get_maintenance_state()
    return MaintenanceState(
        enabled=bool(state.get("enabled")),
        message=state.get("message", ""),
        status_text=state.get("status_text", ""),
        app_version=state.get("app_version", ""),
        retry_after=int(state.get("retry_after", getattr(settings, "MAINTENANCE_RETRY_AFTER", 300))),
        updated_at=state.get("updated_at", datetime.utcnow().isoformat()),
    ).__dict__
