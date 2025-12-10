from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse_lazy
from django_ratelimit.decorators import ratelimit
from django_ratelimit.core import get_usage
import logging

from usermanagement.models import Permission, UserPermission
from utils.logging_utils import StructuredLogger

logger = logging.getLogger(__name__)

def permission_required(permission, *, require_organization: bool = True, ratelimit_enabled: bool = False):
    """
    Organization-aware permission decorator.

    Supports either a tuple of (module, entity, action) for the custom RBAC
    system or a plain permission codename string. Automatically redirects
    unauthenticated users to login and users without an active organization
    to the organization selector.

    Args:
        permission: Permission codename string or (module, entity, action) tuple
        require_organization: Whether organization context is required
        ratelimit_enabled: Whether to apply rate limiting (100 checks/minute per user)
    """

    def decorator(view_func):
        # Apply rate limiting if enabled
        if ratelimit_enabled:
            view_func = ratelimit(key='user', rate='100/m', method='GET', block=True)(view_func)

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return HttpResponseRedirect(
                    f"{reverse_lazy('login')}?next={quote(request.get_full_path())}"
                )

            organization = getattr(request, "organization", None) or user.get_active_organization()
            if require_organization and not organization:
                messages.warning(request, "Select an organization to continue.")
                return HttpResponseRedirect(
                    f"{reverse_lazy('usermanagement:select_organization')}?next={quote(request.get_full_path())}"
                )

            # Check rate limit for permission checks
            if ratelimit_enabled:
                usage = get_usage(request, 'user', '100/m', 'GET')
                if usage['should_limit']:
                    return HttpResponse("Rate limit exceeded for permission checks.", status=429)

            if isinstance(permission, tuple):
                allowed = PermissionUtils.has_permission(user, organization, *permission)
                permission_label = "_".join(permission)
            else:
                allowed = PermissionUtils.has_codename(user, organization, permission)
                permission_label = permission

            if not allowed:
                return HttpResponseForbidden(f"Permission '{permission_label}' is required.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator

class PermissionUtils:
    CACHE_TIMEOUT = 900  # Increased to 15 minutes
    CACHE_VERSION = 1  # Add versioning for cache busting
    logger = StructuredLogger('permissions')

    @staticmethod
    def _cache_key(user_id, organization_id):
        """Versioned cache key to enable global invalidation."""
        return f'user_permissions:v{PermissionUtils.CACHE_VERSION}:{user_id}:{organization_id}'

    @staticmethod
    def get_user_permissions(user, organization):
        """Get permissions with fallback on cache failure."""
        # Superuser check
        if not user or not getattr(user, 'is_authenticated', False):
            return set()

        if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
            return {'*'}  # Use set instead of list

        if not organization:
            return set()

        cache_key = PermissionUtils._cache_key(user.id, organization.id)

        try:
            permissions = cache.get(cache_key)
            if permissions is not None:
                return permissions
        except Exception as e:
            # Log but don't fail - fall through to DB query
            logger.warning(f"Cache read failed for {cache_key}: {e}")

        # Query permissions (existing logic)
        permissions = PermissionUtils._query_permissions(user, organization)

        # Try to cache, but don't fail if it doesn't work
        try:
            cache.set(cache_key, permissions, PermissionUtils.CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Cache write failed for {cache_key}: {e}")

        return permissions

    @staticmethod
    def _query_permissions(user, organization):
        """Separate method for DB query logic."""
        role_permissions = set(
            Permission.objects.filter(
                roles__user_roles__user=user,
                roles__user_roles__organization=organization,
                roles__user_roles__is_active=True,
                roles__is_active=True,
                is_active=True,
            ).values_list('codename', flat=True)
        )

        # Apply overrides with select_related to reduce queries
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

        return role_permissions

    @staticmethod
    def invalidate_user_cache(user_id, organization_id):
        """Invalidate specific user cache."""
        cache.delete(PermissionUtils._cache_key(user_id, organization_id))

    @staticmethod
    def invalidate_all_caches():
        """Global cache bust by incrementing version."""
        PermissionUtils.CACHE_VERSION += 1
        # Persist version to settings or database if needed

    @staticmethod
    def bulk_invalidate(user_ids, organization_id):
        """Efficiently invalidate multiple users."""
        keys = [PermissionUtils._cache_key(uid, organization_id) for uid in user_ids]
        cache.delete_many(keys)

    @staticmethod
    def has_codename(user, organization, permission_codename: str):
        """Check a permission codename against the scoped Role/Permission matrix."""
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "role", None) == "superadmin" or getattr(user, "is_superuser", False):
            return True

        if permission_codename and "." in permission_codename:
            return user.has_perm(permission_codename)

        if not organization:
            return False

        permissions = PermissionUtils.get_user_permissions(user, organization)
        if permissions == {'*'}:  # Handle super admin case
            return True

        return permission_codename in permissions

    @staticmethod
    @ratelimit(key='user', rate='100/m', method='GET', block=True)
    def has_codename_ratelimited(user, organization, permission_codename: str):
        """Rate-limited version of has_codename (100 checks per minute per user)."""
        return PermissionUtils.has_codename(user, organization, permission_codename)

    @staticmethod
    def has_permission(user, organization, module, entity, action):
        codename = f"{module}_{entity}_{action}"
        granted = PermissionUtils.has_codename(user, organization, codename)

        PermissionUtils.logger.log_permission_check(
            user, organization, codename, granted
        )

        return granted

    @staticmethod
    @ratelimit(key='user', rate='100/m', method='GET', block=True)
    def has_permission_ratelimited(user, organization, module, entity, action):
        """Rate-limited version of has_permission (100 checks per minute per user)."""
        return PermissionUtils.has_permission(user, organization, module, entity, action)

    @staticmethod
    def invalidate_cache(user_id, organization_id):
        """Invalidate specific user cache. (Legacy method for backward compatibility)"""
        PermissionUtils.invalidate_user_cache(user_id, organization_id)

    @staticmethod
    def is_org_admin(user, organization):
        """Check if user is an organization admin."""
        if not user or not organization:
            return False
        if getattr(user, "role", None) == "superadmin" or getattr(user, "is_superuser", False):
            return True
        
        # Check for specific org admin permission or role
        # Assuming 'org_admin' role or 'organization_manage' permission
        # Let's check for 'organization_manage' permission which is common for admins
        return PermissionUtils.has_codename(user, organization, 'usermanagement_organization_manage')

def require_permission(module, entity, action):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            organization = request.user.get_active_organization()
            if not organization:
                messages.warning(request, "Please select an active organization to continue.")
                return HttpResponseRedirect(reverse_lazy('usermanagement:select_organization'))
                
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
