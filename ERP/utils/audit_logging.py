"""
Audit Logging Utility

Provides centralized audit logging functionality for tracking user actions
across the application.
"""

import logging
from typing import Optional, Any, Dict

from django.contrib.contenttypes.models import ContentType

from accounting.utils.audit import log_audit_event
from accounting.models import AuditLog

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
        content_type = None
        instance = None
        try:
            content_type = ContentType.objects.get(model=object_type.lower())
            model_class = content_type.model_class()
            if model_class:
                instance = model_class.objects.filter(pk=object_id).first()
        except ContentType.DoesNotExist:
            logger.warning(f"ContentType not found for {object_type}")

        if instance is not None:
            log_audit_event(
                user,
                instance,
                action,
                changes=changes,
                details=details,
                organization=organization,
            )
        else:
            AuditLog.objects.create(
                user=user,
                organization=organization,
                action=action,
                content_type=content_type,
                object_id=object_id,
                changes=changes or {},
                details=details,
                ip_address=None,
            )

        logger.info(f"Audit log created: User {user.username} performed {action} on {object_type} {object_id}")
        
    except Exception as e:
        # Don't fail the main operation if audit logging fails
        logger.error(f"Failed to create audit log: {e}", exc_info=True)
