def active_organization(request):
    """Add the user's active organization to the template context.
    This makes `organization` accessible in header templates without requiring
    every view to use the UserOrganizationMixin explicitly.
    """
    org = None
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        getter = getattr(user, 'get_active_organization', None)
        if callable(getter):
            try:
                org = getter()
            except Exception:
                org = None
    return {'organization': org}
from usermanagement.models import Entity, Module
from usermanagement.utils import PermissionUtils

def permissions(request):
    """Add user permissions to template context."""
    if not request.user.is_authenticated:
        return {
            'user_permissions': {},
            'has_permission': lambda module, entity, action: False,
        }

    organization = request.user.get_active_organization()
    permission_set = PermissionUtils.get_user_permissions(request.user, organization)

    # Special marker for all permissions
    if permission_set == ['*']:
        return {
            'user_permissions': {'*': True},
            'has_permission': lambda module, entity, action: True,
        }

    structured_permissions = {}
    for codename in permission_set:
        try:
            module_code, entity_code, action = codename.split('_', 2)
        except ValueError:
            # Skip malformed codenames but keep processing
            continue

        module_perms = structured_permissions.setdefault(module_code, {})
        entity_perms = module_perms.setdefault(entity_code, set())
        entity_perms.add(action)

    return {
        'user_permissions': structured_permissions,
        'has_permission': lambda module, entity, action: PermissionUtils.has_permission(
            request.user,
            organization,
            module,
            entity,
            action,
        ),
    }

def menu(request):
    """Add menu items to template context."""
    if not request.user.is_authenticated:
        return {'menu_items': []}

    organization = request.user.get_active_organization()
    user = request.user

    # Get all modules with their entities
    modules = Module.objects.filter(
        is_active=True
    ).prefetch_related(
        'entities'
    ).order_by('order')

    menu_items = []
    for module in modules:
        # Get entities for this module - all entities visible to authenticated users
        entities = Entity.objects.filter(
            module=module,
            is_active=True
        ).distinct()

        visible_entities = []
        for entity in entities:
            has_view = PermissionUtils.has_permission(
                user,
                organization,
                module.code,
                entity.code,
                'view',
            )
            if has_view:
                visible_entities.append({
                    'name': entity.name,
                    'code': entity.code,
                    'url': getattr(entity, 'url_pattern', ''),
                    'permissions': {
                        'view': True,
                        'create': PermissionUtils.has_permission(user, organization, module.code, entity.code, 'add'),
                        'edit': PermissionUtils.has_permission(user, organization, module.code, entity.code, 'change'),
                        'delete': PermissionUtils.has_permission(user, organization, module.code, entity.code, 'delete'),
                    }
                })

        if visible_entities:
            menu_items.append({
                'name': module.name,
                'code': module.code,
                'icon': module.icon,
                'entities': visible_entities,
            })

    return {'menu_items': menu_items}
