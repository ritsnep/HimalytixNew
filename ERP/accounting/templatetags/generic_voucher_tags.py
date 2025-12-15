from django import template

register = template.Library()


@register.filter
def widget_type(bound_field):
    widget = getattr(bound_field.field, 'widget', None)
    return widget.__class__.__name__ if widget else ''
