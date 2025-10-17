from django import template
from django.forms import Field, Form
from django.forms.forms import BaseForm
from django.utils.html import format_html

register = template.Library()


@register.filter
def with_css_class(field, css_class):
    """Add CSS class to a form field."""
    return field.as_widget(attrs={"class": css_class})


@register.inclusion_tag('components/base/form_field.html')
def render_field(field, label_class='', field_class='', show_help=True):
    """Render a form field with consistent styling."""
    return {
        'field': field,
        'label_class': label_class,
        'field_class': field_class,
        'show_help': show_help,
        'field_type': field.field.widget.__class__.__name__
    }


@register.inclusion_tag('components/base/pagination.html')
def render_pagination(page_obj, anchor=''):
    """Render pagination controls."""
    return {
        'page_obj': page_obj,
        'anchor': anchor
    }
