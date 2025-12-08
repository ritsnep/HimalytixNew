"""Template context processors for accounting app."""
from typing import Dict, Any


def default_currency(request) -> Dict[str, Any]:
    """Provide `default_currency` and `default_currency_code` to all templates.

    This mirrors the logic in `UserOrganizationMixin.get_context_data` so
    templates rendered from function-based views also receive the values.
    """
    org = getattr(request, "organization", None)
    user = getattr(request, "user", None)

    if not org and user is not None:
        # Try user's active organization as a fallback
        if hasattr(user, "get_active_organization"):
            org = user.get_active_organization()
        else:
            org = getattr(user, "organization", None)

    if not org:
        return {"default_currency": None, "default_currency_code": None}

    return {
        "default_currency": getattr(org, "base_currency_code", None),
        "default_currency_code": getattr(org, "base_currency_code_id", None),
    }
