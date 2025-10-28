"""
Database query optimization utilities
"""
from django.db import connection
from django.db.models import Prefetch
import logging

logger = logging.getLogger(__name__)


def log_queries(func):
    """
    Decorator to log all database queries made by a function.
    Useful for identifying N+1 query problems.
    
    Usage:
        @log_queries
        def my_view(request):
            users = User.objects.all()
            for user in users:
                print(user.profile.bio)  # N+1 query!
    """
    def wrapper(*args, **kwargs):
        from django.conf import settings
        if not settings.DEBUG:
            return func(*args, **kwargs)
        
        # Reset queries
        from django.db import reset_queries
        reset_queries()
        
        # Execute function
        result = func(*args, **kwargs)
        
        # Log queries
        queries = connection.queries
        logger.info(f"{func.__name__} executed {len(queries)} queries")
        for query in queries:
            logger.debug(f"  {query['time']}s: {query['sql'][:100]}")
        
        return result
    return wrapper


def optimize_queryset(queryset, select_related=None, prefetch_related=None):
    """
    Helper to optimize a queryset with select_related and prefetch_related.
    
    Usage:
        qs = User.objects.all()
        qs = optimize_queryset(
            qs,
            select_related=['profile', 'tenant'],
            prefetch_related=['permissions', 'groups']
        )
    """
    if select_related:
        queryset = queryset.select_related(*select_related)
    
    if prefetch_related:
        queryset = queryset.prefetch_related(*prefetch_related)
    
    return queryset


# =============================================================================
# COMMON QUERY OPTIMIZATIONS
# =============================================================================

def get_users_with_profiles(queryset=None):
    """
    Get users with profiles in a single query.
    Prevents N+1 when accessing user.profile.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    qs = queryset or User.objects.all()
    return qs.select_related('profile')


def get_users_with_permissions(queryset=None):
    """
    Get users with permissions prefetched.
    Prevents N+1 when accessing user.user_permissions.all().
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    qs = queryset or User.objects.all()
    return qs.prefetch_related('user_permissions', 'groups__permissions')


def get_tenants_with_users(queryset=None):
    """
    Get tenants with users prefetched.
    Prevents N+1 when accessing tenant.users.all().
    """
    from tenancy.models import Tenant
    
    qs = queryset or Tenant.objects.all()
    return qs.prefetch_related(
        Prefetch('users', queryset=get_users_with_profiles())
    )
