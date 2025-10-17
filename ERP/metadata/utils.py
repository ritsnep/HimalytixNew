import json
import logging
from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.http import HttpRequest
from .loader import get_field_permissions
from .regenerator import get_dynamic_model
from django.conf import settings
from .watcher import WATCHDOG_AVAILABLE

logger = logging.getLogger(__name__)

def validate_form_data(entity_name: str, data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate form data against entity schema.
    
    Args:
        entity_name: Name of the entity
        data: Form data to validate
        
    Returns:
        Dict mapping field names to lists of validation errors
    """
    errors = {}
    
    try:
        # Get the dynamic model
        model = get_dynamic_model(entity_name)
        if not model:
            raise ValueError(f"No model found for entity: {entity_name}")
        
        # Validate data
        try:
            model.parse_obj(data)
        except Exception as e:
            if hasattr(e, 'errors'):
                for error in e.errors():
                    field = error['loc'][0]
                    if field not in errors:
                        errors[field] = []
                    errors[field].append(error['msg'])
            else:
                logger.error(f"Validation error: {str(e)}")
                errors['__all__'] = [str(e)]
                
    except Exception as e:
        logger.error(f"Error validating form data: {str(e)}")
        errors['__all__'] = [str(e)]
        
    return errors

def get_field_permissions_for_user(entity_name: str, request: HttpRequest) -> Dict[str, bool]:
    """
    Get field-level permissions for the current user.
    
    Args:
        entity_name: Name of the entity
        request: HTTP request object
        
    Returns:
        Dict mapping field names to boolean indicating if user has write permission
    """
    try:
        # Get permissions from cache first
        cache_key = f'field_permissions_{entity_name}_{request.user.id}'
        permissions = cache.get(cache_key)
        
        if permissions is None:
            # Get permissions from database
            permissions = get_field_permissions(entity_name, request.user)
            
            # Cache permissions
            cache.set(cache_key, permissions, timeout=3600)
            
        return permissions
        
    except Exception as e:
        logger.error(f"Error getting field permissions: {str(e)}")
        return {}

def apply_field_permissions(form_html: str, permissions: Dict[str, bool]) -> str:
    """
    Apply field permissions to form HTML.
    
    Args:
        form_html: Form HTML string
        permissions: Dict mapping field names to boolean indicating write permission
        
    Returns:
        Modified form HTML with permissions applied
    """
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(form_html, 'html.parser')
        
        # Find all form groups
        for form_group in soup.find_all('div', class_='form-group'):
            field_name = form_group.get('data-field')
            if field_name and field_name in permissions:
                # Find input/select elements
                for element in form_group.find_all(['input', 'select']):
                    if not permissions[field_name]:
                        # Disable field if user doesn't have write permission
                        element['disabled'] = 'disabled'
                        element['readonly'] = 'readonly'
                        
        return str(soup)
        
    except Exception as e:
        logger.error(f"Error applying field permissions: {str(e)}")
        return form_html

def get_form_with_permissions(entity_name: str, request: HttpRequest) -> str:
    """
    Get form HTML with permissions applied for the current user.
    
    Args:
        entity_name: Name of the entity
        request: HTTP request object
        
    Returns:
        Form HTML with permissions applied
    """
    try:
        # Get form template
        from .regenerator import get_form_template
        form_html = get_form_template(entity_name)
        
        # Get permissions
        permissions = get_field_permissions_for_user(entity_name, request)
        
        # Apply permissions
        return apply_field_permissions(form_html, permissions)
        
    except Exception as e:
        logger.error(f"Error getting form with permissions: {str(e)}")
        return ""

def is_watcher_available() -> bool:
    """Check if the file watcher is available."""
    return WATCHDOG_AVAILABLE

def get_watcher_status() -> Dict[str, Any]:
    """Get the current status of the watcher."""
    return {
        'available': is_watcher_available(),
        'enabled': settings.DEBUG and is_watcher_available(),
        'cache_enabled': settings.CACHES.get('default', {}).get('BACKEND') != 'django.core.cache.backends.dummy.DummyCache'
    }

def check_field_permission(user, field_name: str, entity_name: str, action: str = 'view') -> bool:
    """
    Check if user has permission to access a specific field.
    
    Args:
        user: The user to check permissions for
        field_name: Name of the field to check
        entity_name: Name of the entity containing the field
        action: Type of action ('view', 'edit', 'create', 'delete')
        
    Returns:
        bool: True if user has permission, False otherwise
    """
    if not user.is_authenticated:
        return False
        
    # Superusers have all permissions
    if user.is_superuser:
        return True
        
    # Check specific field permissions
    perm_codename = f'can_{action}_{entity_name}_{field_name}'
    return user.has_perm(f'ERP.metadata.{perm_codename}')

def get_field_permissions(user, entity_name: str) -> Dict[str, Dict[str, bool]]:
    """
    Get all field permissions for a user on an entity.
    
    Args:
        user: The user to check permissions for
        entity_name: Name of the entity to check permissions for
        
    Returns:
        Dict mapping field names to their permission status for each action
    """
    if not user.is_authenticated:
        return {}
        
    # Superusers have all permissions
    if user.is_superuser:
        return {
            field_name: {'view': True, 'edit': True, 'create': True, 'delete': True}
            for field_name in get_entity_fields(entity_name)
        }
        
    permissions = {}
    for field_name in get_entity_fields(entity_name):
        permissions[field_name] = {
            action: check_field_permission(user, field_name, entity_name, action)
            for action in ['view', 'edit', 'create', 'delete']
        }
    return permissions

def get_entity_fields(entity_name: str) -> List[str]:
    """Get all field names for an entity."""
    # Try to get from cache first
    cache_key = f'entity_fields_{entity_name}'
    fields = cache.get(cache_key)
    
    if fields is None:
        try:
            from .loader import load_entity_schema
            fields = list(load_entity_schema(entity_name).keys())
            cache.set(cache_key, fields, timeout=3600)  # Cache for 1 hour
        except Exception as e:
            logger.error(f"Error loading fields for entity {entity_name}: {str(e)}")
            fields = []
            
    return fields

def get_field_attributes(field_name: str, entity_name: str) -> Dict[str, Any]:
    """Get additional attributes for a field."""
    try:
        from .loader import load_entity_schema
        schema = load_entity_schema(entity_name)
        return schema.get(field_name, {})
    except Exception as e:
        logger.error(f"Error loading attributes for field {field_name}: {str(e)}")
        return {}

def should_show_field(user, field_name: str, entity_name: str) -> bool:
    """Check if a field should be shown to the user."""
    return check_field_permission(user, field_name, entity_name, 'view')

def can_edit_field(user, field_name: str, entity_name: str) -> bool:
    """Check if a field can be edited by the user."""
    return check_field_permission(user, field_name, entity_name, 'edit')

def get_field_html_attributes(user, field_name: str, entity_name: str) -> Dict[str, str]:
    """
    Get HTML attributes for a field based on user permissions.
    
    Returns:
        Dict of HTML attributes to apply to the field
    """
    attrs = {}
    
    # Check if field should be shown
    if not should_show_field(user, field_name, entity_name):
        attrs['style'] = 'display: none;'
        return attrs
        
    # Add readonly/disabled attributes if user can't edit
    if not can_edit_field(user, field_name, entity_name):
        attrs['readonly'] = 'readonly'
        attrs['disabled'] = 'disabled'
        
    # Add data attributes for HTMX
    attrs['data-field-name'] = field_name
    attrs['data-entity-name'] = entity_name
    
    return attrs 