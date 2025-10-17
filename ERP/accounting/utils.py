from contextlib import contextmanager

_thread_locals = {}

def get_current_request():
    return _thread_locals.get('request')

@contextmanager
def record_request(request):
    _thread_locals['request'] = request
    yield
    _thread_locals.pop('request', None)

def get_current_user():
    request = get_current_request()
    if request:
        return request.user
    return None

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip