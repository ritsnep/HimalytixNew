from utils.calendars import CalendarMode, DateSeedStrategy, get_calendar_mode
from tenancy.models import TenantConfig


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
    return {
        'organization': org,
        'calendar_mode': get_calendar_mode(org, default=CalendarMode.DEFAULT),
        'calendar_date_seed': DateSeedStrategy.normalize(
            getattr(getattr(org, "config", None), "calendar_date_seed", None)
        ),
    }


def theme_branding(request):
    """Add theme branding colors from tenant/organization configuration to template context.
    
    Returns:
        dict: Contains 'brand_color' (org-level or default #1c84ee)
    """
    brand_color = '#1c84ee'  # Default brand color
    
    # Try to get organization-specific brand color
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        try:
            org = getattr(user, 'get_active_organization', lambda: None)()
            if org:
                # Try to get brand color from tenant config
                try:
                    from tenancy.models import Tenant
                    tenant = Tenant.objects.filter(code=org.code).first()
                    if tenant:
                        brand_config = TenantConfig.objects.filter(
                            tenant=tenant,
                            config_key='brand_color'
                        ).first()
                        if brand_config and brand_config.config_value:
                            brand_color = brand_config.config_value
                except Exception:
                    pass
        except Exception:
            pass
    
    return {
        'brand_color': brand_color,
    }
from usermanagement.models import Entity, Module
from usermanagement.utils import PermissionUtils

def permissions(request):
    """Add user permissions to template context."""
    if not request.user.is_authenticated:
        return {
            'user_permissions': set(),
        }

    organization = request.user.get_active_organization()
    permission_set = PermissionUtils.get_user_permissions(request.user, organization)

    # Special marker for all permissions
    if permission_set == {'*'}:
        return {
            'user_permissions': {'*'},
        }

    return {
        'user_permissions': permission_set,
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
