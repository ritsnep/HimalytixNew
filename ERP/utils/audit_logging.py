"""
Audit Logging Utility

Provides centralized audit logging functionality for tracking user actions
across the application.
"""

import logging
from django.contrib.contenttypes.models import ContentType
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)


def log_action(
    user,
    organization,
    action: str,
    object_type: str,
    object_id: int,
    details: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an audit action.
    
    Args:
        user: The user performing the action
        organization: The organization context
        action: The action being performed (e.g., 'approved_journal', 'rejected_journal')
        object_type: The type of object being acted upon (e.g., 'Journal', 'Account')
        object_id: The ID of the object
        details: Optional detailed description of the action
        changes: Optional dictionary of changes made
    """
    try:
        from accounting.models import AuditLog
        
        # Get the content type for the object
        try:
            content_type = ContentType.objects.get(model=object_type.lower())
        except ContentType.DoesNotExist:
            logger.warning(f"ContentType not found for {object_type}")
            content_type = None
        
        # Create audit log entry
        audit_entry = AuditLog.objects.create(
            user=user,
            action=action,
            content_type=content_type,
            object_id=object_id,
            changes=changes or {},
            details=details,
            ip_address=None  # Can be added if request is available
        )
        
        logger.info(
            f"Audit log created: User {user.username} performed {action} "
            f"on {object_type} {object_id}"
        )
        
    except Exception as e:
        # Don't fail the main operation if audit logging fails
        logger.error(f"Failed to create audit log: {e}", exc_info=True)
