"""
Custom template filters for billing app
"""
from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def mul(value, arg):
    """
    Multiply two values
    Usage: {{ quantity|mul:unit_price }}
    """
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, AttributeError):
        return 0
