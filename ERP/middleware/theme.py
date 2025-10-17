from typing import Callable
from django.http import HttpRequest

class ThemeMiddleware:
    """Attach theme preference to request."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request.theme = request.COOKIES.get('theme', 'light')
        response = self.get_response(request)
        return response

def theme(request: HttpRequest) -> dict:
    return {'theme': getattr(request, 'theme', 'light')}