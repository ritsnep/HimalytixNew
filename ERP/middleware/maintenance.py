"""
Middleware to enforce maintenance mode and capture in-flight user context.
"""
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

from utils.maintenance import (
    capture_request_snapshot,
    get_effective_app_version,
    get_maintenance_state,
    pop_snapshot_for_request,
    should_bypass_maintenance,
)

logger = logging.getLogger(__name__)


class MaintenanceModeMiddleware(MiddlewareMixin):
    """
    Enforces MAINTENANCE_MODE.
    - Short-circuits requests with 503 + friendly template/JSON.
    - Captures user/session snapshot before blocking.
    - Surfaces the saved snapshot after maintenance clears.
    """

    def process_request(self, request):
        state = get_maintenance_state()
        request.maintenance_state = state
        request.maintenance_snapshot = None

        if not state.get("enabled"):
            resume_snapshot = pop_snapshot_for_request(request)
            if resume_snapshot:
                request.maintenance_snapshot = resume_snapshot
            return None

        if should_bypass_maintenance(request):
            return None

        snapshot = capture_request_snapshot(request)
        request.maintenance_snapshot = snapshot
        logger.info(
            "maintenance_mode_blocked_request",
            extra={
                "path": request.path,
                "method": request.method,
                "user": getattr(getattr(request, "user", None), "id", None),
            },
        )
        return self._maintenance_response(request, state, snapshot)

    def process_response(self, request, response):
        try:
            version = get_effective_app_version()
            if version:
                response["X-App-Version"] = version

            content_type = response.get("Content-Type", "")
            if content_type.startswith("text/html"):
                response["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"

            snapshot = getattr(request, "maintenance_snapshot", None)
            state = getattr(request, "maintenance_state", None)
            if snapshot and state and not state.get("enabled"):
                response["X-Maintenance-Snapshot"] = "1"
                response["X-Maintenance-Snapshot-Path"] = snapshot.get("path", "")
        except Exception:
            # Never block the response on maintenance bookkeeping.
            logger.exception("maintenance_middleware_response_error")
        return response

    def _maintenance_response(self, request, state: Dict[str, Any], snapshot: Optional[Dict[str, Any]]):
        payload = {
            "detail": state.get("message")
            or "Scheduled maintenance is in progress. Please retry in a few minutes.",
            "status_text": state.get("status_text", ""),
            "retry_after": state.get("retry_after", getattr(settings, "MAINTENANCE_RETRY_AFTER", 300)),
            "app_version": get_effective_app_version(),
            "snapshot": snapshot or {},
            "updated_at": state.get("updated_at"),
        }
        accept_header = request.headers.get("Accept", "")
        wants_json = request.path.startswith("/api/") or "application/json" in accept_header or request.headers.get("HX-Request") == "true"

        if wants_json:
            response = JsonResponse(payload, status=503)
        else:
            response = render(request, "maintenance.html", payload, status=503)

        response["Retry-After"] = str(payload["retry_after"])
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["X-App-Version"] = payload["app_version"]
        return response
