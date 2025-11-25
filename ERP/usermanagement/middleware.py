"""Middleware to attach the active organization/company to the request."""

from usermanagement.models import Organization, UserOrganization


class ActiveOrganizationMiddleware:
    """
    Resolve the current company (organization) for the authenticated user.

    Priority:
      1. request.session['active_organization_id']
      2. request.tenant (if present on request)
      3. user.organization
      4. first active UserOrganization mapping
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = self.get_current_organization(request)
        return self.get_response(request)

    def get_current_organization(self, request):
        org_id = request.session.get("active_organization_id") if hasattr(request, "session") else None
        if org_id:
            organization = Organization.objects.filter(id=org_id).first()
            if organization:
                return organization

        tenant = getattr(request, "tenant", None)
        if tenant:
            organization = Organization.objects.filter(tenant=tenant).first()
            if organization:
                return organization

        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            if getattr(user, "organization_id", None):
                return user.organization
            mapping = (
                UserOrganization.objects.filter(user=user, is_active=True)
                .select_related("organization")
                .first()
            )
            if mapping:
                return mapping.organization

        return None
