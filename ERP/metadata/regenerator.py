import json
import logging
from typing import Dict, Type, Optional
from pydantic import BaseModel, create_model, Field
from django.core.cache import cache
from django.template import Template, Context
from .loader import load_entity_schema, get_entity_metadata
from .persister import EntityProperty

logger = logging.getLogger(__name__)

# Registry for dynamic models
_dynamic_models: Dict[str, Type[BaseModel]] = {}

def get_python_type(sql_type: str) -> Type:
    """Map SQL data type to Python type."""
    type_map = {
        'varchar': str,
        'char': str,
        'text': str,
        'int': int,
        'bigint': int,
        'decimal': float,
        'float': float,
        'double': float,
        'boolean': bool,
        'date': str,  # ISO format date string
        'datetime': str,  # ISO format datetime string
        'timestamp': str,  # ISO format timestamp string
        'json': dict,
        'array': list
    }
    return type_map.get(sql_type.lower(), str)

def get_field_validation(validation_rules: Optional[str]) -> Dict:
    """Parse validation rules into Pydantic field constraints."""
    if not validation_rules:
        return {}
        
    try:
        rules = json.loads(validation_rules)
        constraints = {}
        
        if 'min_length' in rules:
            constraints['min_length'] = rules['min_length']
        if 'max_length' in rules:
            constraints['max_length'] = rules['max_length']
        if 'min' in rules:
            constraints['ge'] = rules['min']
        if 'max' in rules:
            constraints['le'] = rules['max']
        if 'pattern' in rules:
            constraints['regex'] = rules['pattern']
            
        return constraints
    except Exception as e:
        logger.error(f"Error parsing validation rules: {str(e)}")
        return {}

def regenerate_pydantic_models() -> None:
    """Regenerate all Pydantic models from entity schemas."""
    try:
        # Get all entities
        entities = EntityProperty.objects.values_list(
            'entity_name', flat=True
        ).distinct()
        
        for entity_name in entities:
            # Load schema
            fields = load_entity_schema(entity_name, force_refresh=True)
            
            # Build model fields
            model_fields = {}
            for field in fields:
                # Get Python type
                py_type = get_python_type(field.data_type)
                
                # Get validation rules
                validation = get_field_validation(field.validation)
                
                # Create field with metadata
                field_info = {
                    'title': field.label,
                    'description': field.help_text,
                    **validation
                }
                
                # Handle choices
                if field.choices:
                    try:
                        choices = json.loads(field.choices)
                        field_info['enum'] = choices
                    except Exception as e:
                        logger.error(f"Error parsing choices: {str(e)}")
                
                # Create field with default if not required
                if field.required:
                    model_fields[field.name] = (py_type, Field(**field_info))
                else:
                    default = field.default_value
                    if default is not None:
                        try:
                            # Try to convert default to proper type
                            default = py_type(default)
                        except (ValueError, TypeError):
                            default = None
                    model_fields[field.name] = (Optional[py_type], Field(default=default, **field_info))
            
            # Create model
            model = create_model(entity_name, **model_fields)
            _dynamic_models[entity_name] = model
            
            # Cache model schema
            cache.set(
                f'entity_schema_{entity_name}',
                model.model_json_schema(),
                timeout=3600
            )
            
        logger.info("Successfully regenerated Pydantic models")
        
    except Exception as e:
        logger.error(f"Error regenerating Pydantic models: {str(e)}")
        raise

def get_dynamic_model(entity_name: str) -> Optional[Type[BaseModel]]:
    """Get a dynamic model by name."""
    return _dynamic_models.get(entity_name)

def generate_form_template(entity_name: str) -> str:
    """Generate HTML form template for an entity."""
    try:
        # Load schema and metadata
        fields = load_entity_schema(entity_name)
        metadata = get_entity_metadata(entity_name)
        
        # Create template context
        context = {
            'entity_name': entity_name,
            'entity_label': metadata.get('label', entity_name),
            'fields': fields
        }
        
        # Load and render template
        template_str = """
        <form id="{{ entity_name }}_form" class="entity-form">
            <div class="form-header">
                <h2>{{ entity_label }}</h2>
            </div>
            
            <div class="form-body">
                {% for field in fields %}
                <div class="form-group" data-field="{{ field.name }}">
                    <label for="{{ field.name }}">{{ field.label }}</label>
                    {% if field.help_text %}
                    <small class="form-text text-muted">{{ field.help_text }}</small>
                    {% endif %}
                    
                    {% if field.choices %}
                    <select class="form-control" 
                            name="{{ field.name }}"
                            {% if field.required %}required{% endif %}
                            {% if not field.is_editable %}disabled{% endif %}
                            hx-get="/metadata/field/validate/{{ field.name }}/"
                            hx-trigger="change"
                            hx-target="#{{ field.name }}-error"
                            hx-indicator="#{{ field.name }}-indicator">
                        <option value="">Select {{ field.label }}</option>
                        {% for choice in field.choices %}
                        <option value="{{ choice.value }}">{{ choice.label }}</option>
                        {% endfor %}
                    </select>
                    <div id="{{ field.name }}-error" class="error-message"></div>
                    <div id="{{ field.name }}-indicator" class="htmx-indicator">
                        <span class="loading-spinner"></span>
                    </div>
                    {% else %}
                    <input type="text" 
                           class="form-control"
                           name="{{ field.name }}"
                           {% if field.required %}required{% endif %}
                           {% if not field.is_editable %}disabled{% endif %}
                           {% if field.validation %}data-validation="{{ field.validation }}"{% endif %}
                           hx-get="/metadata/field/validate/{{ field.name }}/"
                           hx-trigger="keyup changed delay:500ms"
                           hx-target="#{{ field.name }}-error"
                           hx-indicator="#{{ field.name }}-indicator">
                    <div id="{{ field.name }}-error" class="error-message"></div>
                    <div id="{{ field.name }}-indicator" class="htmx-indicator">
                        <span class="loading-spinner"></span>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
            
            <div class="form-footer">
                <button type="submit" class="btn btn-primary">
                    Save
                    <span id="form-indicator" class="htmx-indicator">
                        <span class="loading-spinner"></span>
                    </span>
                </button>
                <button type="button" class="btn btn-secondary" onclick="resetForm()">
                    Reset
                </button>
            </div>
        </form>
        """
        
        template = Template(template_str)
        html = template.render(Context(context))
        
        # Cache the form
        cache.set(f'entity_form_{entity_name}', html, timeout=3600)
        
        return html
        
    except Exception as e:
        logger.error(f"Error generating form template: {str(e)}")
        raise

def get_form_template(entity_name: str) -> str:
    """Get cached form template or generate new one."""
    cached_form = cache.get(f'entity_form_{entity_name}')
    if cached_form:
        return cached_form
    return generate_form_template(entity_name) 