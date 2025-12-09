from django import template
from django.urls import reverse, NoReverseMatch
import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.simple_tag
def safe_url(viewname, *args, **kwargs):
    """Safely reverse URL, returning empty string on failure.

    Usage: {% safe_url 'accounting:delivery_note_list' as url %}
           {% if url %}<a href="{{ url }}">Link</a>{% endif %}
    """
    try:
        return reverse(viewname, args=args, kwargs=kwargs)
    except NoReverseMatch:
        logger.warning(f"Failed to reverse URL: {viewname}")
        return ''
    except Exception as e:
        logger.error(f"Error reversing URL {viewname}: {e}")
        return ''

@register.filter
def safe_permission_check(user, permission_string):
    """Safe permission check with error handling."""
    try:
        from usermanagement.templatetags.permission_tags import has_permission_filter
        return has_permission_filter(user, permission_string)
    except Exception as e:
        logger.error(f"Permission check failed for {permission_string}: {e}")
        return False  # Fail closed