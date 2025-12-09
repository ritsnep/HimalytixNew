"""
Query optimization utilities for list views.

This module provides optimized query patterns for common list view operations,
particularly for permission-related queries and data loading.
"""

from django.db.models import Prefetch, Q, Count, Exists, OuterRef, Subquery
from django.core.cache import cache
from usermanagement.models import (
    CustomUser, Organization, UserRole, UserPermission,
    Permission, Role, UserOrganization
)
from functools import wraps
import time
import logging

logger = logging.getLogger(__name__)

class QueryOptimizer:
    """Utility class for optimizing database queries in list views."""

    @staticmethod
    def get_optimized_user_queryset():
        """Get optimized queryset for user list views with related data."""
        return CustomUser.objects.select_related(
            'organization'  # Primary organization
        ).prefetch_related(
            Prefetch(
                'user_organizations',
                queryset=UserOrganization.objects.select_related('organization'),
                to_attr='org_memberships'
            ),
            Prefetch(
                'user_roles',
                queryset=UserRole.objects.select_related('role', 'organization'),
                to_attr='role_assignments'
            ),
            Prefetch(
                'user_permissions',
                queryset=UserPermission.objects.select_related('permission', 'organization'),
                to_attr='permission_overrides'
            )
        )

    @staticmethod
    def get_optimized_role_queryset():
        """Get optimized queryset for role list views."""
        return Role.objects.select_related(
            'organization'
        ).prefetch_related(
            Prefetch(
                'permissions',
                queryset=Permission.objects.select_related('module', 'entity'),
                to_attr='permission_list'
            ),
            Prefetch(
                'user_roles',
                queryset=UserRole.objects.select_related('user'),
                to_attr='assigned_users'
            )
        ).annotate(
            user_count=Count('user_roles', distinct=True),
            permission_count=Count('permissions', distinct=True)
        )

    @staticmethod
    def get_optimized_organization_queryset():
        """Get optimized queryset for organization list views."""
        return Organization.objects.prefetch_related(
            Prefetch(
                'user_organizations',
                queryset=UserOrganization.objects.select_related('user'),
                to_attr='members'
            ),
            Prefetch(
                'roles',
                queryset=Role.objects.prefetch_related('permissions'),
                to_attr='available_roles'
            )
        ).annotate(
            member_count=Count('user_organizations', distinct=True),
            role_count=Count('roles', distinct=True)
        )

    @staticmethod
    def get_permission_filtered_queryset(user, organization, base_queryset, permission_codename):
        """
        Filter queryset based on user permissions, optimized to avoid N+1 queries.

        Args:
            user: User object
            organization: Organization object
            base_queryset: Base queryset to filter
            permission_codename: Permission required to view items
        """
        from usermanagement.utils import PermissionUtils

        # Check if user has the required permission
        if not PermissionUtils.has_codename(user, organization, permission_codename):
            # Return empty queryset if no permission
            return base_queryset.none()

        # For superusers/admins, return all
        if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
            return base_queryset

        # For regular users, you might want to filter based on ownership/assignment
        # This depends on your specific business logic
        return base_queryset

    @staticmethod
    def optimize_list_view_queryset(view_class, queryset_method_name='get_queryset'):
        """
        Decorator to optimize list view querysets.

        Usage:
            @QueryOptimizer.optimize_list_view_queryset
            class MyListView(ListView):
                def get_queryset(self):
                    return MyModel.objects.all()
        """
        def decorator(cls):
            original_method = getattr(cls, queryset_method_name)

            @wraps(original_method)
            def optimized_get_queryset(self):
                queryset = original_method(self)

                # Add select_related/prefetch_related based on model
                model_name = self.model.__name__ if hasattr(self, 'model') else 'Unknown'

                if model_name == 'CustomUser':
                    queryset = QueryOptimizer.get_optimized_user_queryset()
                elif model_name == 'Role':
                    queryset = QueryOptimizer.get_optimized_role_queryset()
                elif model_name == 'Organization':
                    queryset = QueryOptimizer.get_optimized_organization_queryset()

                # Add permission filtering if user and org are available
                if hasattr(self, 'request') and self.request:
                    user = self.request.user
                    organization = getattr(self.request, 'organization', None) or user.get_active_organization()

                    # Try to determine appropriate permission
                    permission_map = {
                        'CustomUser': 'usermanagement_user_view',
                        'Role': 'usermanagement_role_view',
                        'Organization': 'usermanagement_organization_view',
                    }

                    required_permission = permission_map.get(model_name)
                    if required_permission:
                        queryset = QueryOptimizer.get_permission_filtered_queryset(
                            user, organization, queryset, required_permission
                        )

                return queryset

            setattr(cls, queryset_method_name, optimized_get_queryset)
            return cls

        return decorator

class PerformanceMonitor:
    """Monitor query performance and cache effectiveness."""

    def __init__(self):
        self.query_count = 0
        self.query_time = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def __enter__(self):
        from django.db import connection
        from django.core.cache import cache

        self.start_queries = len(connection.queries)
        self.start_time = time.time()

        # Monkey patch cache to count hits/misses
        self.original_get = cache.get
        self.original_set = cache.set

        def monitored_get(key, default=None, version=None):
            result = self.original_get(key, default, version)
            if result is not None:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
            return result

        cache.get = monitored_get
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from django.db import connection
        from django.core.cache import cache

        # Restore original cache methods
        cache.get = self.original_get

        self.query_count = len(connection.queries) - self.start_queries
        self.query_time = time.time() - self.start_time

    def get_stats(self):
        """Get performance statistics."""
        return {
            'query_count': self.query_count,
            'query_time_ms': round(self.query_time * 1000, 2),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': (self.cache_hits / (self.cache_hits + self.cache_misses) * 100)
                           if (self.cache_hits + self.cache_misses) > 0 else 0
        }

def monitor_query_performance(func):
    """Decorator to monitor query performance of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with PerformanceMonitor() as monitor:
            result = func(*args, **kwargs)

        stats = monitor.get_stats()
        logger.info(
            f"Query performance for {func.__name__}",
            extra={
                'query_count': stats['query_count'],
                'query_time_ms': stats['query_time_ms'],
                'cache_hit_rate': stats['cache_hit_rate'],
                'function': func.__name__
            }
        )

        return result
    return wrapper

# Optimized query patterns for common operations

def get_users_with_permissions_optimized(org_id):
    """Get users with their permissions - optimized version."""
    return CustomUser.objects.filter(
        user_organizations__organization_id=org_id,
        user_organizations__is_active=True
    ).select_related(
        'organization'
    ).prefetch_related(
        Prefetch(
            'user_roles__role__permissions',
            queryset=Permission.objects.select_related('module', 'entity'),
            to_attr='role_permissions'
        ),
        Prefetch(
            'user_permissions__permission',
            queryset=Permission.objects.select_related('module', 'entity'),
            to_attr='direct_permissions'
        )
    )

def get_roles_with_usage_stats_optimized(org_id):
    """Get roles with usage statistics - optimized version."""
    return Role.objects.filter(
        organization_id=org_id
    ).prefetch_related(
        'permissions__module',
        'permissions__entity'
    ).annotate(
        user_count=Count('user_roles', filter=Q(user_roles__is_active=True)),
        permission_count=Count('permissions')
    )

def bulk_check_permissions_optimized(user_ids, org_id, permission_codename):
    """Check permissions for multiple users efficiently."""
    from usermanagement.utils import PermissionUtils

    # Get all relevant data in bulk
    users = CustomUser.objects.filter(id__in=user_ids).prefetch_related(
        Prefetch(
            'user_roles',
            queryset=UserRole.objects.filter(
                organization_id=org_id,
                is_active=True
            ).select_related('role'),
            to_attr='active_roles'
        ),
        Prefetch(
            'user_permissions',
            queryset=UserPermission.objects.filter(
                organization_id=org_id
            ).select_related('permission'),
            to_attr='permission_overrides'
        )
    )

    results = {}
    for user in users:
        # Use cached permission check
        results[user.id] = PermissionUtils.has_codename(user, Organization.objects.get(id=org_id), permission_codename)

    return results