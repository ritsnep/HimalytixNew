from rest_framework.permissions import BasePermission

class IsOrganizationMember(BasePermission):
    """Allows access only to users associated with an organization."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "organization", None))