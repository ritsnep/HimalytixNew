"""
Rate limiting configuration for Himalytix ERP API
"""
from django.core.cache import cache
from functools import wraps
from django.http import JsonResponse


def rate_limit_key(group, request):
    """
    Generate cache key for rate limiting.
    Format: ratelimit:{group}:{user_id or ip}
    """
    if request.user.is_authenticated:
        return f'ratelimit:{group}:{request.user.id}'
    else:
        # Use IP address for anonymous users
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return f'ratelimit:{group}:{ip}'


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    pass
