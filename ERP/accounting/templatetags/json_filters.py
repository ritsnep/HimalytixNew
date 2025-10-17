from django import template
import json

register = template.Library()

@register.filter
def json_parse(value):
    """
    Parses a JSON string and returns a Python object.
    Useful for displaying JSON errors from forms.
    """
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}