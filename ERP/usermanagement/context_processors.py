from usermanagement.models import Entity, Module

def permissions(request):
    """Add user permissions to template context."""
    if not request.user.is_authenticated:
        return {'user_permissions': {}}

    # EntityPermission model was removed - permission check disabled
    # TODO: Implement new permission system
    user_permissions = {}
    if request.user.is_superuser:
        # Superusers get all permissions
        entities = Entity.objects.all()
        for entity in entities:
            user_permissions[entity.code] = {'view', 'create', 'edit', 'delete'}

    return {
        'user_permissions': user_permissions,
        'has_permission': lambda entity_code, action: (
            request.user.is_superuser or (entity_code in user_permissions and 
            action in user_permissions[entity_code])
        )
    }

def menu(request):
    """Add menu items to template context."""
    if not request.user.is_authenticated:
        return {'menu_items': []}

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

        if entities.exists():
            menu_items.append({
                'name': module.name,
                'code': module.code,
                'icon': module.icon,
                'entities': [
                    {
                        'name': entity.name,
                        'code': entity.code,
                        'url': entity.url_pattern,
                        'permissions': {
                            'view': True,
                            'create': request.user.is_superuser,
                            'edit': request.user.is_superuser,
                            'delete': request.user.is_superuser,
                        }
                    }
                    for entity in entities
                ]
            })

    return {'menu_items': menu_items} 