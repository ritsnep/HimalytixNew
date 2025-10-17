from django import template
from usermanagement.utils import PermissionUtils

register = template.Library()

@register.filter
def has_permission(user, permission_string):
    if not user or not user.is_authenticated:
        return False
    if hasattr(user, 'role') and user.role == 'superadmin':
        return True
        
    module, entity, action = permission_string.split('_')
    return PermissionUtils.has_permission(
        user,
        user.get_active_organization(),
        module,
        entity,
        action
    )

@register.simple_tag
def has_permission(user, permission_string):
    if not user or not user.is_authenticated:
        return False
    if hasattr(user, 'role') and user.role == 'superadmin':
        return True
        
    module, entity, action = permission_string.split('_')
    return PermissionUtils.has_permission(
        user,
        user.get_active_organization(),
        module,
        entity,
        action
    )
