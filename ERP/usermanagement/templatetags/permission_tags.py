from django import template

from usermanagement.utils import PermissionUtils

register = template.Library()


def _parse_permission_string(permission_string):
    parts = permission_string.split('_')
    if len(parts) < 3:
        raise ValueError(f"Invalid permission string '{permission_string}'. Expected format module_entity_action.")
    module = parts[0]
    entity = parts[1]
    action = '_'.join(parts[2:])
    return module, entity, action


def _check_permission(user, permission_string):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
        return True

    try:
        module, entity, action = _parse_permission_string(permission_string)
    except ValueError:
        return False

    return PermissionUtils.has_permission(
        user,
        user.get_active_organization(),
        module,
        entity,
        action,
    )


@register.filter(name='has_permission')
def has_permission_filter(user, permission_string):
    return _check_permission(user, permission_string)


@register.simple_tag(name='user_has_permission')
def has_permission_tag(user, permission_string):
    return _check_permission(user, permission_string)
