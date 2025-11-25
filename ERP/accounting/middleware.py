import logging
from .utils import record_request
from usermanagement.models import Organization

logger = logging.getLogger(__name__)

class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Respect organization already resolved by upstream middleware
        if getattr(request, "organization", None):
            return self.get_response(request)

        if hasattr(request, 'tenant') and request.tenant:
            try:
                organization = Organization.objects.get(tenant=request.tenant)
                request.organization = organization
                logger.info(f"Organization '{organization.name}' attached to request for tenant '{request.tenant.name}'.")
            except Organization.DoesNotExist:
                logger.warning(f"No organization found for tenant '{request.tenant.name}'.")
                request.organization = None
        else:
            logger.warning("No tenant found on request.")
            request.organization = None

        with record_request(request):
            response = self.get_response(request)
        return response
