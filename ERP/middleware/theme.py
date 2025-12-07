from typing import Callable

from django.conf import settings
from django.http import HttpRequest

class ThemeMiddleware:
    """Attach theme preference to request."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request.theme = request.COOKIES.get('theme') or getattr(
            settings, "UI_THEME_DEFAULT", "light"
        )
        request.text_scale = request.COOKIES.get('text_scale') or getattr(
            settings, "UI_TEXT_SCALE_DEFAULT", "m"
        )
        response = self.get_response(request)
        return response

def theme(request: HttpRequest) -> dict:
    return {
        'theme': getattr(request, 'theme', 'light'),
        'text_scale': getattr(request, 'text_scale', 'm'),
        'ui_theme_default': getattr(settings, 'UI_THEME_DEFAULT', 'light'),
        'ui_text_scale_default': getattr(settings, 'UI_TEXT_SCALE_DEFAULT', 'm'),
        'ui_font_family_default': getattr(settings, 'UI_FONT_FAMILY_DEFAULT', ''),
        'ui_topbar_default': getattr(settings, 'UI_TOPBAR_DEFAULT', 'light'),
    }