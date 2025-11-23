from django import template

register = template.Library()


@register.filter
def attr(obj, name):
    """Access an attribute dynamically in templates."""
    return getattr(obj, name, "")
