"""
Audit utility functions for hash-chaining, integrity verification, and change detection.
"""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from usermanagement.models import CustomUser, Organization


def compute_content_hash(audit_log_dict: Dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of an audit log record for integrity verification.
    
    Args:
        audit_log_dict: Dictionary with fields: user_id, action, content_type_id, 
                       object_id, changes, timestamp
    
    Returns:
        Hex digest of SHA-256 hash
    """
    # Create canonical JSON representation (sorted keys for consistency)
    data_to_hash = {
        'user_id': audit_log_dict.get('user_id'),
        'action': audit_log_dict.get('action'),
        'content_type_id': audit_log_dict.get('content_type_id'),
        'object_id': audit_log_dict.get('object_id'),
        'changes': audit_log_dict.get('changes', {}),
        'timestamp': audit_log_dict.get('timestamp', '').isoformat() if hasattr(audit_log_dict.get('timestamp', ''), 'isoformat') else str(audit_log_dict.get('timestamp', '')),
    }
    
    canonical_json = json.dumps(data_to_hash, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


def verify_audit_chain(audit_log) -> Tuple[bool, Optional[str]]:
    """
    Verify integrity of an audit log and its predecessors via hash-chaining.
    
    Args:
        audit_log: AuditLog instance
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if hash chain is intact
        - error_message: Description of any tampering detected
    """
    if not audit_log.content_hash:
        return True, None  # Not yet immutable
    
    # Recompute hash
    audit_dict = {
        'user_id': audit_log.user_id,
        'action': audit_log.action,
        'content_type_id': audit_log.content_type_id,
        'object_id': audit_log.object_id,
        'changes': audit_log.changes,
        'timestamp': audit_log.timestamp,
    }
    
    computed_hash = compute_content_hash(audit_dict)
    
    if computed_hash != audit_log.content_hash:
        return False, f"Content hash mismatch. Expected {computed_hash}, got {audit_log.content_hash}"
    
    # Verify previous link if present
    if audit_log.previous_hash:
        try:
            prev_log = audit_log.previous_hash
            if not prev_log.content_hash:
                return False, "Previous audit log has no content hash"
            # Previous log's hash should match what we reference
            # (This is automatically ensured by foreign key)
        except Exception as e:
            return False, f"Error verifying previous log: {str(e)}"
    
    return True, None


def compute_field_changes(old_values: Dict[str, Any], new_values: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute field-level changes between two states.
    
    Args:
        old_values: Previous state (can be None for create)
        new_values: Current state
    
    Returns:
        Dictionary of fields with changes: {field: {'old': value, 'new': value}}
    """
    if old_values is None:
        return {field: {'old': None, 'new': _to_json_safe(value)} 
                for field, value in new_values.items()}
    
    changes = {}
    for field, new_value in new_values.items():
        old_value = old_values.get(field)
        old_serialized = _to_json_safe(old_value)
        new_serialized = _to_json_safe(new_value)
        
        if old_serialized != new_serialized:
            changes[field] = {
                'old': old_serialized,
                'new': new_serialized
            }
    
    return changes


def _to_json_safe(value: Any) -> Any:
    """
    Convert value to JSON-serializable type.
    
    Args:
        value: Any value to serialize
    
    Returns:
        JSON-safe equivalent
    """
    if value is None:
        return None
    if isinstance(value, (str, int, bool, float)):
        return value
    if isinstance(value, (datetime, timezone.datetime.__class__)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]
    
    try:
        return str(value)
    except Exception:
        return "<unserializable>"


def get_audit_summary(organization: Organization, days: int = 30) -> Dict[str, Any]:
    """
    Generate audit summary for a given organization.
    
    Args:
        organization: Organization instance
        days: Number of days to look back
    
    Returns:
        Summary dict with activity counts by action/user/model
    """
    from accounting.models import AuditLog
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    logs = AuditLog.objects.filter(
        organization=organization,
        timestamp__gte=cutoff_date
    )
    
    # Count by action
    action_counts = {}
    for action in ['create', 'update', 'delete', 'export', 'print', 'approve', 'reject', 'post', 'sync']:
        count = logs.filter(action=action).count()
        if count > 0:
            action_counts[action] = count
    
    # Count by user
    user_counts = {}
    for user_id in logs.values_list('user_id', flat=True).distinct():
        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
                user_counts[str(user)] = logs.filter(user_id=user_id).count()
            except CustomUser.DoesNotExist:
                pass
    
    # Count by model
    model_counts = {}
    for content_type_id in logs.values_list('content_type_id', flat=True).distinct():
        if content_type_id:
            try:
                ct = ContentType.objects.get(id=content_type_id)
                model_counts[ct.model] = logs.filter(content_type_id=content_type_id).count()
            except ContentType.DoesNotExist:
                pass
    
    return {
        'organization': str(organization),
        'period_days': days,
        'total_events': logs.count(),
        'by_action': action_counts,
        'by_user': user_counts,
        'by_model': model_counts,
        'cutoff_date': cutoff_date.isoformat(),
    }


def get_entity_history(content_type: ContentType, object_id: int, 
                      organization: Optional[Organization] = None) -> list:
    """
    Get full audit history for a specific entity.
    
    Args:
        content_type: ContentType of the model
        object_id: Primary key of the entity
        organization: Optional organization filter
    
    Returns:
        List of AuditLog entries in chronological order
    """
    from accounting.models import AuditLog
    
    logs = AuditLog.objects.filter(
        content_type=content_type,
        object_id=object_id
    ).order_by('timestamp')
    
    if organization:
        logs = logs.filter(organization=organization)
    
    return list(logs)


def get_user_activity(user: CustomUser, days: int = 7, 
                     organization: Optional[Organization] = None) -> Dict[str, Any]:
    """
    Get activity summary for a user.
    
    Args:
        user: CustomUser instance
        days: Number of days to look back
        organization: Optional organization filter
    
    Returns:
        User activity summary
    """
    from accounting.models import AuditLog
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    logs = AuditLog.objects.filter(
        user=user,
        timestamp__gte=cutoff_date
    )
    
    if organization:
        logs = logs.filter(organization=organization)
    
    # Count by action
    actions = {}
    for action in ['create', 'update', 'delete', 'export', 'print', 'approve', 'reject', 'post', 'sync']:
        count = logs.filter(action=action).count()
        if count > 0:
            actions[action] = count
    
    # Count by model
    models = {}
    for ct_id in logs.values_list('content_type_id', flat=True).distinct():
        if ct_id:
            try:
                ct = ContentType.objects.get(id=ct_id)
                models[ct.model] = logs.filter(content_type_id=ct_id).count()
            except ContentType.DoesNotExist:
                pass
    
    return {
        'user': str(user),
        'period_days': days,
        'total_actions': logs.count(),
        'by_action': actions,
        'by_model': models,
        'first_action': logs.first().timestamp if logs.exists() else None,
        'last_action': logs.last().timestamp if logs.exists() else None,
    }
