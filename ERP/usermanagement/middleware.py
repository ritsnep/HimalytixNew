"""Middleware to attach the active organization/company to the request."""

from usermanagement.models import Organization, UserOrganization
from utils.calendars import CalendarMode, get_calendar_mode


class ActiveOrganizationMiddleware:
    """Resolve the current organization for the authenticated user only from memberships."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        organization = self._resolve_organization(request)
        request.organization = organization
        request.calendar_mode = get_calendar_mode(organization, default=CalendarMode.DEFAULT)
        user = getattr(request, "user", None)
        if user and hasattr(user, "set_active_organization"):
            user.set_active_organization(organization)
        return self.get_response(request)

    def _resolve_organization(self, request):
        session = request.session if hasattr(request, "session") else None
        tenant = getattr(request, "tenant", None)
        user = getattr(request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            if session:
                session.pop("active_organization_id", None)
            return None

        memberships = (
            UserOrganization.objects.filter(user=user, is_active=True)
            .select_related("organization", "organization__tenant")
        )

        def _return_mapping(mapping):
            if not mapping:
                return None
            if session:
                session["active_organization_id"] = mapping.organization_id
            return mapping.organization

        org_id = session.get("active_organization_id") if session else None
        if org_id:
            scoped = memberships.filter(organization_id=org_id)
            if tenant:
                scoped = scoped.filter(organization__tenant=tenant)
            mapping = scoped.first()
            if mapping:
                return _return_mapping(mapping)
            if user.is_superuser:
                org_qs = Organization.objects.filter(id=org_id)
                if tenant:
                    org_qs = org_qs.filter(tenant=tenant)
                organization = org_qs.first()
                if organization:
                    return organization
            if session:
                session.pop("active_organization_id", None)

        if tenant:
            mapping = memberships.filter(organization__tenant=tenant).first()
            resolved = _return_mapping(mapping)
            if resolved:
                return resolved

        return _return_mapping(memberships.first())
