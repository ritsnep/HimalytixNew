from django import template

from django.utils.html import format_html

register = template.Library()


@register.filter
def widget_type(bound_field):
    if not hasattr(bound_field, "field"):
        return ""
    widget = getattr(bound_field.field, "widget", None)
    return widget.__class__.__name__ if widget else ""


@register.filter
def add_class(bound_field, css_class):
    if not bound_field:
        return ""
    widget = bound_field.field.widget
    attrs = widget.attrs.copy()
    existing = attrs.get("class", "")
    if existing:
        attrs["class"] = f"{existing} {css_class}"
    else:
        attrs["class"] = css_class
    return format_html("{}", bound_field.as_widget(attrs=attrs))


@register.filter
def status_badge_class(status_value):
    if status_value in ("done", "succeeded", "success"):
        return "success"
    if status_value in ("failed", "error"):
        return "danger"
    return "secondary"


@register.filter
def get_field(form, field_name):
    if not form or not field_name:
        return ""
    try:
        return form[field_name]
    except Exception:
        return ""
