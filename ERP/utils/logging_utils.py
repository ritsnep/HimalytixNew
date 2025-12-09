import logging
import json
from django.conf import settings

class StructuredLogger:
    """Centralized structured logging."""

    def __init__(self, name):
        self.logger = logging.getLogger(name)

    def log_permission_check(self, user, organization, permission, granted):
        """Log permission checks for audit."""
        if not settings.LOG_PERMISSION_CHECKS:
            return

        self.logger.info(json.dumps({
            'event': 'permission_check',
            'user': user.username,
            'user_id': user.id,
            'organization': organization.code if organization else None,
            'permission': permission,
            'granted': granted,
        }))

    def log_permission_denied(self, user, view, permission):
        """Log permission denials."""
        self.logger.warning(json.dumps({
            'event': 'permission_denied',
            'user': user.username,
            'user_id': user.id,
            'view': view,
            'permission': permission,
        }))

    def log_cache_miss(self, cache_key):
        """Log cache misses."""
        self.logger.debug(json.dumps({
            'event': 'cache_miss',
            'key': cache_key,
        }))