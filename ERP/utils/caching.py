"""
Caching utilities for Himalytix ERP
"""
from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json


def cache_key(*args, **kwargs):
    """
    Generate a consistent cache key from arguments.
    
    Usage:
        key = cache_key('user', user_id=123, tenant='acme')
        # Returns: 'himalytix:user:123:acme'
    """
    parts = [settings.CACHES['default']['KEY_PREFIX']]
    parts.extend(str(arg) for arg in args)
    parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    return ':'.join(parts)


def cache_result(timeout=None, key_prefix=''):
    """
    Decorator to cache function results.
    
    Usage:
        @cache_result(timeout=300, key_prefix='user_profile')
        def get_user_profile(user_id):
            return expensive_database_query(user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key_str = hashlib.md5(':'.join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            result = cache.get(cache_key_str)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            ttl = timeout or settings.CACHE_TTL['default']
            cache.set(cache_key_str, result, ttl)
            return result
        return wrapper
    return decorator


def invalidate_cache(pattern):
    """
    Invalidate cache keys matching a pattern.
    
    Usage:
        invalidate_cache('user:123:*')
    """
    # Note: This requires Redis SCAN command
    # For other backends, you'd need a different approach
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection('default')
        prefix = settings.CACHES['default']['KEY_PREFIX']
        full_pattern = f"{prefix}:{pattern}"
        
        cursor = 0
        while True:
            cursor, keys = conn.scan(cursor, match=full_pattern, count=100)
            if keys:
                conn.delete(*keys)
            if cursor == 0:
                break
    except ImportError:
        # Fallback: Clear entire cache if not using Redis
        cache.clear()


# =============================================================================
# PRE-DEFINED CACHE FUNCTIONS
# =============================================================================

def cache_user_permissions(user_id, permissions):
    """Cache user permissions for 1 hour."""
    key = cache_key('permissions', user_id=user_id)
    cache.set(key, permissions, settings.CACHE_TTL['long'])


def get_cached_user_permissions(user_id):
    """Get cached user permissions."""
    key = cache_key('permissions', user_id=user_id)
    return cache.get(key)


def cache_tenant_settings(tenant_id, settings_dict):
    """Cache tenant settings for 1 day."""
    key = cache_key('tenant_settings', tenant_id=tenant_id)
    cache.set(key, settings_dict, settings.CACHE_TTL['permanent'])


def get_cached_tenant_settings(tenant_id):
    """Get cached tenant settings."""
    key = cache_key('tenant_settings', tenant_id=tenant_id)
    return cache.get(key)


def invalidate_user_cache(user_id):
    """Invalidate all cache entries for a user."""
    invalidate_cache(f'*user_id:{user_id}*')


def invalidate_tenant_cache(tenant_id):
    """Invalidate all cache entries for a tenant."""
    invalidate_cache(f'*tenant_id:{tenant_id}*')
