"""
Template tags for bulk import system
"""
from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    """Get value from dictionary by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''

@register.filter
def model_verbose_name(model):
    """Get verbose name for a model"""
    if hasattr(model, '_meta'):
        return model._meta.verbose_name
    return str(model)

@register.filter
def model_verbose_name_plural(model):
    """Get verbose name plural for a model"""
    if hasattr(model, '_meta'):
        return model._meta.verbose_name_plural
    return str(model)

@register.simple_tag
def get_bulk_field_help(field_config, field_name):
    """Get help text for a bulk import field"""
    help_text = field_config.get('help_text', '')
    
    if not help_text:
        field_type = field_config.get('type', 'str')
        if field_type == 'fk':
            model = field_config.get('model')
            if model:
                help_text = f'Reference to {model._meta.verbose_name}'
        elif field_type == 'bool':
            help_text = 'true/false or yes/no'
        elif field_type == 'choice':
            choices = field_config.get('choices', [])
            if choices:
                help_text = f'Choices: {", ".join([c[0] for c in choices[:3]])}'
    
    return help_text

@register.inclusion_tag('accounting/partials/bulk_import_field_info.html')
def render_bulk_field_info(field_name, field_config):
    """Render field information for bulk import help"""
    return {
        'field_name': field_name,
        'field_config': field_config,
        'required': field_config.get('required', False),
        'field_type': field_config.get('type', 'str'),
        'help_text': get_bulk_field_help(field_config, field_name),
    }
