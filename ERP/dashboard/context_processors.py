"""Context processors for dashboard templates."""

from typing import Dict

from utils.branding import get_branding_from_request


def branding_context(request) -> Dict[str, dict]:
	"""Expose tenant-aware branding information to every template."""
	return {"branding": get_branding_from_request(request)}
