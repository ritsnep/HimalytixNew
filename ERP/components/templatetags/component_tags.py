"""Template tags for dynamic components"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_attr(obj, attr):
    """Get object attribute, supports nested attributes with dot notation"""
    try:
        for part in attr.split('.'):
            obj = getattr(obj, part)
        if callable(obj):
            obj = obj()
        return obj
    except (AttributeError, TypeError):
        return ''

@register.simple_tag
def render_field(field, **kwargs):
    """Render form field with bootstrap classes and custom attributes"""
    css_class = 'form-control'
    if field.errors:
        css_class += ' is-invalid'
    
    # Add Bootstrap classes based on field type
    if field.field.widget.__class__.__name__ == 'CheckboxInput':
        css_class = 'form-check-input'
    elif field.field.widget.__class__.__name__ == 'Select':
        css_class = 'form-select'
        
    field.field.widget.attrs.update({
        'class': css_class,
        **kwargs
    })
    
    return mark_safe(field.as_widget())

@register.simple_tag
def render_column_header(column, current_ordering=None):
    """Render sortable column header"""
    if not column.get('sortable', True):
        return column['label']
        
    field = column['field']
    current_order = current_ordering[0] if current_ordering else ''
    is_current = abs(current_order) == field
    order_type = 'desc' if is_current and current_order > 0 else 'asc'
    
    return mark_safe(f'''
        <a href="?ordering={'+-'[order_type == 'asc']}{field}" 
           class="text-dark">
            {column['label']}
            {'<i class="fas fa-sort-' + order_type + '"></i>' if is_current else ''}
        </a>
    ''')

@register.inclusion_tag('components/base/pagination.html')
def render_pagination(page_obj):
    """Render bootstrap pagination"""
    return {
        'page_obj': page_obj,
        'page_range': page_obj.paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=2,
            on_ends=1
        )
    }
