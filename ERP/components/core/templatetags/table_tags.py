from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def render_column_header(column, current_sort=None, sort_desc=False):
    """Render a sortable column header."""
    if not column.sortable:
        return format_html('&lt;th class="{}"&gt;{}&lt;/th&gt;',
                         ' '.join(column.css_classes or []), 
                         column.label)
                         
    sort_class = ''
    if current_sort == column.name:
        sort_class = 'sort-desc' if sort_desc else 'sort-asc'
        
    return format_html(
        '&lt;th class="sortable {} {}"&gt;'
        '&lt;a href="?sort={}&amp;desc={}"&gt;{}&lt;/a&gt;'
        '&lt;/th&gt;',
        sort_class,
        ' '.join(column.css_classes or []),
        column.name,
        'false' if current_sort == column.name and sort_desc else 'true',
        column.label
    )
    
    
@register.simple_tag
def render_column_value(column, value, obj=None):
    """Render a column value using its template or format function."""
    if column.template:
        template = template.loader.get_template(column.template)
        return template.render({'value': value, 'obj': obj})
        
    if column.format_func and callable(column.format_func):
        return column.format_func(value, obj)
        
    return value
