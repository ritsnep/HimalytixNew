from rest_framework.permissions import BasePermission


def _resolve_request_organization(request):
    organization = getattr(request, "organization", None)
    if organization:
        return organization
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if hasattr(user, "get_active_organization"):
        organization = user.get_active_organization()
        if organization:
            setattr(request, "organization", organization)
            if hasattr(user, "set_active_organization"):
                user.set_active_organization(organization)
        return organization
    return None


class IsOrganizationMember(BasePermission):
    """Allows access only to users associated with an organization."""

    def has_permission(self, request, view):
        return _resolve_request_organization(request) is not None