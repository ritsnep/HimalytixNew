from django.core.cache import cache
from functools import wraps
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib import messages

from usermanagement.models import Permission, UserPermission


def permission_required(permission_codename):
    """Decorator that checks a user's Django permission by codename."""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perm(permission_codename):
                return HttpResponseForbidden()
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

class PermissionUtils:
    CACHE_TIMEOUT = 300  # seconds

    @staticmethod
    def _cache_key(user_id, organization_id):
        return f'user_permissions:{user_id}:{organization_id}'

    @staticmethod
    def get_user_permissions(user, organization):
        # Super admin has all permissions
        if not user or not getattr(user, 'is_authenticated', False):
            return set()

        if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
            return ['*']  # Special marker for all permissions

        if not organization:
            return set()

        cache_key = PermissionUtils._cache_key(user.id, organization.id)
        permissions = cache.get(cache_key)
        if permissions is not None:
            return permissions

        role_permissions = set(
            Permission.objects.filter(
                roles__user_roles__user=user,
                roles__user_roles__organization=organization,
                roles__user_roles__is_active=True,
                roles__is_active=True,
                is_active=True,
            ).values_list('codename', flat=True)
        )

        # Apply user-specific overrides
        overrides = UserPermission.objects.filter(
            user=user,
            organization=organization,
        ).select_related('permission')

        for override in overrides:
            codename = override.permission.codename
            if override.is_granted:
                role_permissions.add(codename)
            else:
                role_permissions.discard(codename)

        cache.set(cache_key, role_permissions, PermissionUtils.CACHE_TIMEOUT)
        return role_permissions

    @staticmethod
    def has_permission(user, organization, module, entity, action):
        if not user or not user.is_authenticated:
            return False
        if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
            return True

        if not organization:
            return False

        permissions = PermissionUtils.get_user_permissions(user, organization)
        if permissions == ['*']:  # Handle super admin case
            return True

        codename = f"{module}_{entity}_{action}"
        return codename in permissions

    @staticmethod
    def invalidate_cache(user_id, organization_id):
        cache.delete(PermissionUtils._cache_key(user_id, organization_id))

def require_permission(module, entity, action):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            organization = request.user.get_active_organization()
            if not organization:
                messages.warning(request, "Please select an active organization to continue.")
                return HttpResponseRedirect(reverse_lazy('select_organization'))
                
            if not PermissionUtils.has_permission(
                request.user, 
                organization,
                module,
                entity,
                action
            ):
                messages.error(request, "You don't have permission to access this page.")
                return HttpResponseRedirect(reverse_lazy('dashboard'))
            return view_func(self, request, *args, **kwargs)
        return _wrapped_view
    return decorator 


def get_menu(user):
    menu = []
    for permission in user.user_permissions.all():
        codename = permission.codename
        if codename.startswith("menu_"):
            url = codename.split("menu_", 1)[1]
            menu.append({"label": permission.name, "url": url})
    return menu


def get_form_fields(user, form):
    fields = []
    for field in form.fields:
        if user.has_perm(f'edit_{field}'):
            fields.append(field)
    return fields 
