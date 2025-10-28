"""
Structured Logging Middleware for Himalytix ERP
Adds request context to all log entries using structlog
"""
import structlog
import uuid
from django.utils.deprecation import MiddlewareMixin


logger = structlog.get_logger(__name__)


class StructuredLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to add request context to structured logs.
    
    Adds:
    - request_id: Unique identifier for each request
    - user_id: ID of authenticated user (if any)
    - ip_address: Client IP address
    - method: HTTP method
    - path: Request path
    """

    def process_request(self, request):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.request_id = request_id
        
        # Extract user info
        user_id = None
        username = "anonymous"
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
            username = request.user.username
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        # Bind context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            method=request.method,
            path=request.path,
        )
        
        logger.info(
            "request_started",
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    def process_response(self, request, response):
        logger.info(
            "request_finished",
            status_code=response.status_code,
        )
        return response

    def process_exception(self, request, exception):
        logger.error(
            "request_exception",
            exception=str(exception),
            exception_type=type(exception).__name__,
        )
