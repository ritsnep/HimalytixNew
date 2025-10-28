"""
Security middleware for Himalytix ERP
Implements rate limiting and security headers
"""
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
import time


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware for API endpoints.
    
    Rules:
    - API endpoints: 100 requests/hour per user
    - Login endpoint: 5 requests/minute per IP
    - Admin endpoints: 50 requests/hour per user
    """
    
    def process_request(self, request):
        # Skip rate limiting for health checks
        if request.path in ['/health/', '/health/ready/', '/health/live/']:
            return None
        
        # Determine rate limit based on endpoint
        if request.path.startswith('/api/'):
            limit, window = 100, 3600  # 100 requests per hour
            group = 'api'
        elif request.path == '/accounts/login/':
            limit, window = 5, 60  # 5 requests per minute
            group = 'login'
        elif request.path.startswith('/admin/'):
            limit, window = 50, 3600  # 50 requests per hour
            group = 'admin'
        else:
            return None  # No rate limit for other endpoints
        
        # Generate cache key
        if request.user.is_authenticated:
            key = f'ratelimit:{group}:{request.user.id}'
        else:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
            key = f'ratelimit:{group}:{ip}'
        
        # Check current request count
        current = cache.get(key, {'count': 0, 'reset': time.time() + window})
        
        # Reset if window expired
        if time.time() > current['reset']:
            current = {'count': 0, 'reset': time.time() + window}
        
        # Increment count
        current['count'] += 1
        cache.set(key, current, window)
        
        # Check limit
        if current['count'] > limit:
            retry_after = int(current['reset'] - time.time())
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'detail': f'Too many requests. Please try again in {retry_after} seconds.',
                'retry_after': retry_after
            }, status=429, headers={
                'Retry-After': str(retry_after),
                'X-RateLimit-Limit': str(limit),
                'X-RateLimit-Remaining': '0',
                'X-RateLimit-Reset': str(int(current['reset']))
            })
        
        # Add rate limit headers to response
        request.rate_limit_remaining = limit - current['count']
        request.rate_limit_reset = int(current['reset'])
        
        return None
    
    def process_response(self, request, response):
        # Add rate limit headers if available
        if hasattr(request, 'rate_limit_remaining'):
            response['X-RateLimit-Remaining'] = str(request.rate_limit_remaining)
            response['X-RateLimit-Reset'] = str(request.rate_limit_reset)
        
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    
    Headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: max-age=31536000; includeSubDomains
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: geolocation=(), microphone=(), camera=()
    """
    
    def process_response(self, request, response):
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # XSS protection (legacy, but still used)
        response['X-XSS-Protection'] = '1; mode=block'
        
        # HSTS (only if HTTPS)
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Referrer policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy (restrict browser features)
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=(), payment=()'
        
        # Content Security Policy (CSP)
        # Note: Adjust based on your actual requirements
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "img-src 'self' data: https:",
            "font-src 'self' https://cdn.jsdelivr.net",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        return response
