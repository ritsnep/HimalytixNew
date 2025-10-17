from django.core.cache import cache
from django.http import HttpResponseTooManyRequests
import time

class AJAXRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            user_key = f"rate_limit_{request.user.id}"
            current_time = time.time()
            request_history = cache.get(user_key, [])
            
            # Clean old requests
            request_history = [t for t in request_history 
                             if current_time - t < 60]

            if len(request_history) >= 60:  # Max 60 requests per minute
                return HttpResponseTooManyRequests()

            request_history.append(current_time)
            cache.set(user_key, request_history, 60)

        return self.get_response(request)