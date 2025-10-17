from contextlib import contextmanager

_thread_locals = {}

def get_current_request():
    """Get the current request from thread locals"""
    return _thread_locals.get('request')

@contextmanager
def record_request(request):
    """Context manager to store request in thread locals"""
    _thread_locals['request'] = request
    yield
    _thread_locals.pop('request', None)

def get_current_user():
    """Get the current user from request"""
    request = get_current_request()
    if request:
        return request.user
    return None

def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip