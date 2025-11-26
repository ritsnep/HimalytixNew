"""Context processors for dashboard templates."""

from typing import Dict

from utils.branding import get_branding_from_request
from utils.maintenance import get_effective_app_version, get_maintenance_state


def branding_context(request) -> Dict[str, dict]:
    """Expose tenant-aware branding information to every template."""
    return {"branding": get_branding_from_request(request)}


def runtime_context(request) -> Dict[str, object]:
    """
    Provide runtime flags that templates/JS need:
    - app_version: used by JS to trigger cache busting on change
    - maintenance state/snapshot: used to surface resume hints after downtime
    """
    snapshot = getattr(request, "maintenance_snapshot", None)
    state = getattr(request, "maintenance_state", None) or get_maintenance_state()
    return {
        "app_version": get_effective_app_version(),
        "maintenance_state": state,
        "maintenance_snapshot": snapshot,
    }
