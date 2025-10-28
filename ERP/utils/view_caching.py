"""
Advanced caching decorators and utilities for Django views and APIs
"""

import hashlib
import time
from functools import wraps
from typing import Optional, Callable, Any, List
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page as django_cache_page
from django.views.decorators.vary import vary_on_headers
from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework.response import Response
from rest_framework.request import Request as DRFRequest
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# VIEW CACHING DECORATORS
# =============================================================================

def cache_view(timeout: int = 300, key_prefix: str = "view"):
    """
    Cache entire view response for specified timeout.
    
    Args:
        timeout: Cache timeout in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key
    
    Usage:
        @cache_view(timeout=600)
        def my_view(request):
            return render(request, 'template.html')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Build cache key from URL and query params
            cache_key = _build_view_cache_key(
                request, 
                key_prefix, 
                view_func.__name__
            )
            
            # Try to get cached response
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_response
            
            # Execute view and cache response
            logger.debug(f"Cache MISS: {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            # Only cache successful responses
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        
        return wrapped_view
    return decorator


def cache_view_per_user(timeout: int = 300):
    """
    Cache view response per authenticated user.
    
    Args:
        timeout: Cache timeout in seconds
    
    Usage:
        @cache_view_per_user(timeout=300)
        def dashboard(request):
            return render(request, 'dashboard.html', context)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Include user ID in cache key
            user_id = request.user.id if request.user.is_authenticated else 'anonymous'
            cache_key = f"view:user:{user_id}:{view_func.__name__}:{request.path}"
            
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache HIT (user-specific): {cache_key}")
                return cached_response
            
            logger.debug(f"Cache MISS (user-specific): {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        
        return wrapped_view
    return decorator


def cache_view_per_tenant(timeout: int = 300):
    """
    Cache view response per tenant in multi-tenant system.
    
    Args:
        timeout: Cache timeout in seconds
    
    Usage:
        @cache_view_per_tenant(timeout=600)
        def tenant_dashboard(request):
            return render(request, 'tenant_dashboard.html')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get tenant from request (adjust based on your multi-tenant setup)
            tenant_id = getattr(request, 'tenant_id', 'default')
            cache_key = f"view:tenant:{tenant_id}:{view_func.__name__}:{request.path}"
            
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache HIT (tenant-specific): {cache_key}")
                return cached_response
            
            logger.debug(f"Cache MISS (tenant-specific): {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            if response.status_code == 200:
                cache.set(cache_key, response, timeout)
            
            return response
        
        return wrapped_view
    return decorator


# =============================================================================
# API RESPONSE CACHING
# =============================================================================

def cache_api_response(timeout: int = 300, vary_on: Optional[List[str]] = None):
    """
    Cache DRF API responses with optional header variation.
    
    Args:
        timeout: Cache timeout in seconds
        vary_on: List of headers to vary cache on (e.g., ['Accept-Language'])
    
    Usage:
        @cache_api_response(timeout=600, vary_on=['Accept-Language'])
        @api_view(['GET'])
        def api_endpoint(request):
            return Response(data)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Build cache key including vary headers
            vary_headers = vary_on or []
            cache_key = _build_api_cache_key(request, view_func.__name__, vary_headers)
            
            # Try cache
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug(f"API Cache HIT: {cache_key}")
                return Response(cached_data)
            
            # Execute view
            logger.debug(f"API Cache MISS: {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            # Cache successful responses
            if isinstance(response, Response) and response.status_code == 200:
                cache.set(cache_key, response.data, timeout)
            
            return response
        
        return wrapped_view
    return decorator


def cache_api_list(timeout: int = 300, per_page: bool = True):
    """
    Cache paginated API list responses.
    
    Args:
        timeout: Cache timeout in seconds
        per_page: Include page number in cache key
    
    Usage:
        @cache_api_list(timeout=300, per_page=True)
        def list_entries(self, request):
            return Response(entries)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Build cache key with page number
            page = request.query_params.get('page', '1') if per_page else 'all'
            page_size = request.query_params.get('page_size', '50')
            cache_key = f"api:list:{view_func.__name__}:page:{page}:size:{page_size}"
            
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug(f"API List Cache HIT: {cache_key}")
                return Response(cached_data)
            
            logger.debug(f"API List Cache MISS: {cache_key}")
            response = view_func(request, *args, **kwargs)
            
            if isinstance(response, Response) and response.status_code == 200:
                cache.set(cache_key, response.data, timeout)
            
            return response
        
        return wrapped_view
    return decorator


# =============================================================================
# ETAG SUPPORT
# =============================================================================

def etag_support(etag_func: Optional[Callable] = None):
    """
    Add ETag support to API endpoints for conditional requests.
    
    Args:
        etag_func: Custom function to calculate ETag (default: hash response data)
    
    Usage:
        @etag_support()
        @api_view(['GET'])
        def get_entry(request, entry_id):
            entry = get_object_or_404(JournalEntry, id=entry_id)
            return Response(serializer.data)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Execute view
            response = view_func(request, *args, **kwargs)
            
            # Only add ETag for successful GET requests
            if request.method != 'GET' or response.status_code != 200:
                return response
            
            # Calculate ETag
            if etag_func:
                etag_value = etag_func(request, response)
            else:
                # Default: hash response data
                if isinstance(response, Response):
                    content = str(response.data).encode('utf-8')
                else:
                    content = response.content
                
                etag_value = hashlib.md5(content).hexdigest()
            
            # Check If-None-Match header
            client_etag = request.META.get('HTTP_IF_NONE_MATCH')
            if client_etag and client_etag.strip('"') == etag_value:
                # Return 304 Not Modified
                if isinstance(response, Response):
                    response = Response(status=304)
                else:
                    response = HttpResponse(status=304)
            
            # Add ETag header
            response['ETag'] = f'"{etag_value}"'
            
            return response
        
        return wrapped_view
    return decorator


def last_modified_support(last_modified_func: Callable):
    """
    Add Last-Modified header support for conditional requests.
    
    Args:
        last_modified_func: Function to get last modified timestamp
    
    Usage:
        def get_entry_last_modified(request, entry_id):
            entry = JournalEntry.objects.get(id=entry_id)
            return entry.updated_at
        
        @last_modified_support(get_entry_last_modified)
        @api_view(['GET'])
        def get_entry(request, entry_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get last modified timestamp
            last_modified = last_modified_func(request, *args, **kwargs)
            
            if last_modified:
                # Format as HTTP date
                from django.utils.http import http_date
                last_modified_str = http_date(last_modified.timestamp())
                
                # Check If-Modified-Since header
                if_modified_since = request.META.get('HTTP_IF_MODIFIED_SINCE')
                if if_modified_since and if_modified_since == last_modified_str:
                    # Return 304 Not Modified
                    return HttpResponse(status=304)
            
            # Execute view
            response = view_func(request, *args, **kwargs)
            
            # Add Last-Modified header
            if last_modified and response.status_code == 200:
                response['Last-Modified'] = last_modified_str
            
            return response
        
        return wrapped_view
    return decorator


# =============================================================================
# CACHE WARMING
# =============================================================================

def warm_cache(cache_key: str, data_func: Callable, timeout: int = 300):
    """
    Pre-populate cache with data (cache warming).
    
    Args:
        cache_key: Cache key to populate
        data_func: Function that returns data to cache
        timeout: Cache timeout in seconds
    
    Usage:
        def get_dashboard_data():
            return expensive_calculation()
        
        warm_cache('dashboard:main', get_dashboard_data, timeout=600)
    """
    try:
        data = data_func()
        cache.set(cache_key, data, timeout)
        logger.info(f"Cache warmed: {cache_key}")
        return True
    except Exception as e:
        logger.error(f"Cache warming failed for {cache_key}: {e}")
        return False


def warm_cache_batch(cache_specs: List[dict]):
    """
    Warm multiple cache entries in batch.
    
    Args:
        cache_specs: List of dicts with 'key', 'data_func', 'timeout'
    
    Usage:
        warm_cache_batch([
            {'key': 'users:list', 'data_func': get_users, 'timeout': 300},
            {'key': 'stats:daily', 'data_func': get_stats, 'timeout': 600},
        ])
    """
    results = {}
    for spec in cache_specs:
        cache_key = spec['key']
        data_func = spec['data_func']
        timeout = spec.get('timeout', 300)
        
        results[cache_key] = warm_cache(cache_key, data_func, timeout)
    
    success_count = sum(results.values())
    logger.info(f"Cache warming: {success_count}/{len(cache_specs)} successful")
    
    return results


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _build_view_cache_key(request: HttpRequest, prefix: str, view_name: str) -> str:
    """Build cache key for view."""
    query_string = request.META.get('QUERY_STRING', '')
    path = request.path
    
    # Hash query string for shorter keys
    query_hash = hashlib.md5(query_string.encode()).hexdigest()[:8] if query_string else 'none'
    
    return f"{prefix}:{view_name}:{path}:qs:{query_hash}"


def _build_api_cache_key(
    request: DRFRequest, 
    view_name: str, 
    vary_headers: List[str]
) -> str:
    """Build cache key for API response."""
    key_parts = [
        'api',
        view_name,
        request.path,
    ]
    
    # Add vary header values
    for header in vary_headers:
        header_value = request.META.get(f'HTTP_{header.upper().replace("-", "_")}', '')
        if header_value:
            key_parts.append(f"{header}:{header_value}")
    
    # Add query params
    query_params = dict(request.query_params)
    if query_params:
        params_str = str(sorted(query_params.items()))
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        key_parts.append(f"params:{params_hash}")
    
    return ":".join(key_parts)


def invalidate_view_cache(view_name: str, path: str = None):
    """
    Invalidate cached view responses.
    
    Args:
        view_name: Name of the view function
        path: Optional path to invalidate (None = all paths)
    """
    if path:
        pattern = f"view:{view_name}:{path}:*"
    else:
        pattern = f"view:{view_name}:*"
    
    # This requires django-redis
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache entries for {view_name}")
            return len(keys)
    except ImportError:
        logger.warning("django-redis not available, cannot invalidate cache pattern")
    
    return 0


def get_cache_stats() -> dict:
    """
    Get cache statistics (requires django-redis).
    
    Returns:
        Dict with cache stats (hits, misses, keys, memory)
    """
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        info = redis_conn.info()
        
        return {
            'hits': info.get('keyspace_hits', 0),
            'misses': info.get('keyspace_misses', 0),
            'hit_rate': info.get('keyspace_hits', 0) / max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1) * 100,
            'keys': redis_conn.dbsize(),
            'memory_used': info.get('used_memory_human', 'N/A'),
            'memory_peak': info.get('used_memory_peak_human', 'N/A'),
        }
    except ImportError:
        return {'error': 'django-redis not available'}
