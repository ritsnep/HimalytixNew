from functools import wraps
from django.http import Http404
from django.http import HttpRequest, HttpResponse
from typing import Callable

def require_htmx(view_func: Callable[[HttpRequest], HttpResponse]) -> Callable[[HttpRequest], HttpResponse]:
    """Ensure the request comes from HTMX."""
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if request.headers.get('HX-Request') != 'true':
            raise Http404()
        return view_func(request, *args, **kwargs)
    return _wrapped