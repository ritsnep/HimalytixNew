from django.http import HttpResponseTooManyRequests
from django.shortcuts import render
from django_ratelimit.core import get_usage

def rate_limit_exceeded(request, exception):
    """View to handle rate limit exceeded errors."""
    usage = get_usage(request, 'user', '100/m', 'GET')

    return render(request, '429.html', {
        'retry_after': 60,  # seconds
        'limit': '100 requests per minute',
        'reset_time': 'next minute',
    }, status=429)