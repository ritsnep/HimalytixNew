from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag(takes_context=True)
def render_column_header(context, column):
    """Render a sortable column header"""
    request = context['request']
    if not column.get('sortable', True):
        return column['label']
    
    current_sort = request.GET.get('sort', '')
    is_current = current_sort.lstrip('-') == column['field']
    is_desc = is_current and current_sort.startswith('-')
    
    # Build the sort URL
    params = request.GET.copy()
    sort_value = f"{'-' if not is_desc else ''}{column['field']}"
    params['sort'] = sort_value
    
    html = f'''
        <a href="?{params.urlencode()}" class="text-dark">
            {column['label']}
            {f'<i class="fas fa-sort-{("down" if is_desc else "up")}"></i>' if is_current else ''}
        </a>
    '''
    return mark_safe(html)

@register.simple_tag
def render_column_value(item, column):
    """Render a column value with optional template"""
    value = item
    for part in column['field'].split('.'):
        value = getattr(value, part, None)
        if callable(value):
            value = value()
            
    if not value and value != 0:
        return ''
    
    if template := column.get('template'):
        t = template.Template(template)
        c = template.Context({'value': value, 'item': item})
        return t.render(c)
        
    if formatter := column.get('formatter'):
        return formatter(value)
        
    return value

@register.filter
def get_attr(obj, attr):
    """Get nested object attribute"""
    try:
        for part in attr.split('.'):
            obj = getattr(obj, part)
            if callable(obj):
                obj = obj()
        return obj
    except (AttributeError, TypeError):
        return ''
