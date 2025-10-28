from django.contrib.contenttypes.models import ContentType
from accounting.models import AuditLog
from django.forms.models import model_to_dict
import datetime
from decimal import Decimal

def convert_dates_to_strings(obj):
    """Backward-compatible name: convert common types to JSON-safe values.

    - datetime/date -> ISO string
    - Decimal -> float (or str if float not desired)
    - dict/list/tuple/set -> recursively converted
    - Other non-serializable -> str(obj)
    """
    if isinstance(obj, dict):
        return {k: convert_dates_to_strings(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [convert_dates_to_strings(i) for i in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    # Primitive JSON-safe types pass through
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # Fallback to string to avoid JSON errors
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"

def get_changed_data(old_instance, new_data):
    """
    Compares an old model instance with new data and returns a dictionary
    of changed fields with their old and new values.
    """
    changes = {}
    old_data = model_to_dict(old_instance) if old_instance else {}

    for field_name, new_value in new_data.items():
        old_value = old_data.get(field_name)
        
        # Handle cases where values might be objects (e.g., ForeignKey instances)
        # Compare their primary keys if they are model instances
        if hasattr(old_value, 'pk') and hasattr(new_value, 'pk'):
            if old_value.pk != new_value.pk:
                changes[field_name] = {'old': str(old_value), 'new': str(new_value)}
        elif str(old_value) != str(new_value): # Simple string comparison for other types
            changes[field_name] = {'old': str(old_value), 'new': str(new_value)}
            
    return changes

def log_audit_event(user, model_instance, action, changes=None, details=None, ip_address=None):
    """
    Logs an audit event for a given model instance.
    """
    content_type = ContentType.objects.get_for_model(model_instance)
    cleaned_changes = convert_dates_to_strings(changes or {})
    AuditLog.objects.create(
        user=user,
        content_type=content_type,
        object_id=model_instance.pk,
        action=action,
        changes=cleaned_changes,
        details=details,
        ip_address=ip_address
    )