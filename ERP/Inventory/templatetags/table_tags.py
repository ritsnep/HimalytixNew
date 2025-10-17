from django import template

register = template.Library()

@register.filter
def getattribute(obj, attr):
    """Get attribute of an object dynamically from template."""
    return getattr(obj, attr, None)

@register.filter
def times(value, arg):
    """Multiply value by arg (for indentation, etc)."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def px(value):
    """Append 'px' to a value for CSS indentation."""
    try:
        return f"{int(value)}px"
    except (ValueError, TypeError):
        return "0px" 