import json
import logging
from typing import Dict, Any, Optional
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.template.loader import render_to_string
from .utils import validate_form_data, get_form_with_permissions
from .loader import get_entity_metadata, load_entity_schema
from .regenerator import get_dynamic_model, regenerate_pydantic_models
from .persister import upsert_entity_properties
from .utils import (
    get_field_permissions,
    get_field_html_attributes,
    get_watcher_status,
    should_show_field,
    can_edit_field
)

logger = logging.getLogger(__name__)

def is_htmx(request: HttpRequest) -> bool:
    """Check if the request is from HTMX."""
    return request.headers.get('HX-Request') == 'true'

@login_required
@require_http_methods(['GET'])
def get_entity_form(request: HttpRequest, entity_name: str) -> HttpResponse:
    """
    Get form HTML for an entity with permissions applied.
    """
    try:
        # Get entity metadata
        metadata = get_entity_metadata(entity_name)
        if not metadata:
            if is_htmx(request):
                return HttpResponse(
                    f'<div class="alert alert-danger">Entity not found: {entity_name}</div>',
                    status=404
                )
            return JsonResponse({
                'error': f'Entity not found: {entity_name}'
            }, status=404)
            
        # Get form with permissions
        form_html = get_form_with_permissions(entity_name, request)
        if not form_html:
            if is_htmx(request):
                return HttpResponse(
                    f'<div class="alert alert-danger">Error generating form for entity: {entity_name}</div>',
                    status=500
                )
            return JsonResponse({
                'error': f'Error generating form for entity: {entity_name}'
            }, status=500)
            
        if is_htmx(request):
            return render(request, 'metadata/entity_form.html', {
                'entity_name': entity_name,
                'metadata': metadata,
                'form_html': form_html
            })
            
        return JsonResponse({
            'form_html': form_html,
            'metadata': metadata
        })
        
    except Exception as e:
        logger.error(f"Error getting entity form: {str(e)}")
        if is_htmx(request):
            return HttpResponse(
                f'<div class="alert alert-danger">Error: {str(e)}</div>',
                status=500
            )
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(['POST'])
def validate_entity_form(request: HttpRequest, entity_name: str) -> HttpResponse:
    """
    Validate form data for an entity.
    """
    try:
        # Parse request data
        data = json.loads(request.body)
        
        # Validate data
        errors = validate_form_data(entity_name, data)
        
        if errors:
            if is_htmx(request):
                error_html = render_to_string('metadata/form_errors.html', {
                    'errors': errors
                })
                return HttpResponse(error_html, status=422)
            return JsonResponse({
                'valid': False,
                'errors': errors
            })
            
        if is_htmx(request):
            return HttpResponse(
                '<div class="alert alert-success">Form is valid!</div>',
                headers={'HX-Redirect': f'/metadata/entity/{entity_name}/form/'}
            )
            
        return JsonResponse({
            'valid': True
        })
        
    except json.JSONDecodeError:
        if is_htmx(request):
            return HttpResponse(
                '<div class="alert alert-danger">Invalid JSON data</div>',
                status=400
            )
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error validating entity form: {str(e)}")
        if is_htmx(request):
            return HttpResponse(
                f'<div class="alert alert-danger">Error: {str(e)}</div>',
                status=500
            )
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def get_entity_schema(request: HttpRequest, entity_name: str) -> HttpResponse:
    """
    Get JSON schema for an entity.
    """
    try:
        # Get the dynamic model
        model = get_dynamic_model(entity_name)
        if not model:
            if is_htmx(request):
                return HttpResponse(
                    f'<div class="alert alert-danger">No model found for entity: {entity_name}</div>',
                    status=404
                )
            return JsonResponse({
                'error': f'No model found for entity: {entity_name}'
            }, status=404)
            
        # Get JSON schema
        schema = model.model_json_schema()
        
        if is_htmx(request):
            return render(request, 'metadata/schema_modal.html', {
                'schema': schema
            })
            
        return JsonResponse({
            'schema': schema
        })
        
    except Exception as e:
        logger.error(f"Error getting entity schema: {str(e)}")
        if is_htmx(request):
            return HttpResponse(
                f'<div class="alert alert-danger">Error: {str(e)}</div>',
                status=500
            )
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(['GET'])
def validate_field(request: HttpRequest, entity_name: str, field_name: str) -> HttpResponse:
    """
    Validate a single field value.
    """
    try:
        # Get field value from request
        value = request.GET.get('value', '')
        
        # Get the dynamic model
        model = get_dynamic_model(entity_name)
        if not model:
            return HttpResponse(
                f'<div class="error-message">No model found for entity: {entity_name}</div>',
                status=404
            )
            
        # Create a partial data dict with just this field
        data = {field_name: value}
        
        try:
            # Try to validate just this field
            model.parse_obj(data)
            return HttpResponse('')  # Empty response means valid
        except Exception as e:
            if hasattr(e, 'errors'):
                for error in e.errors():
                    if error['loc'][0] == field_name:
                        return HttpResponse(
                            f'<div class="error-message">{error["msg"]}</div>',
                            status=422
                        )
            return HttpResponse(
                f'<div class="error-message">Invalid value</div>',
                status=422
            )
            
    except Exception as e:
        logger.error(f"Error validating field: {str(e)}")
        return HttpResponse(
            f'<div class="error-message">Error: {str(e)}</div>',
            status=500
        )

@login_required
@require_http_methods(["GET"])
def get_form_html(request, entity_name: str) -> HttpResponse:
    """Get HTML for an entity form with proper permissions."""
    try:
        # Get field permissions for user
        permissions = get_field_permissions(request.user, entity_name)
        
        # Get schema
        schema = load_entity_schema(entity_name)
        
        # Generate form HTML with permissions
        form_html = []
        for field_name, field_schema in schema.items():
            # Skip fields user can't view
            if not should_show_field(request.user, field_name, entity_name):
                continue
                
            # Get HTML attributes based on permissions
            attrs = get_field_html_attributes(request.user, field_name, entity_name)
            
            # Generate field HTML
            field_html = f'<div class="form-group">'
            field_html += f'<label for="{field_name}">{field_schema.get("label", field_name)}</label>'
            
            # Add field with proper attributes
            field_html += f'<input type="{field_schema.get("type", "text")}" '
            field_html += f'name="{field_name}" id="{field_name}" '
            field_html += f'class="form-control" '
            
            # Add all attributes
            for attr_name, attr_value in attrs.items():
                field_html += f'{attr_name}="{attr_value}" '
                
            field_html += '/>'
            field_html += '</div>'
            
            form_html.append(field_html)
            
        # Add HTMX attributes
        form_html = f'<form hx-post="/metadata/validate/{entity_name}/" hx-swap="outerHTML">' + \
                   ''.join(form_html) + \
                   '<button type="submit" class="btn btn-primary">Submit</button></form>'
                   
        return HttpResponse(form_html)
        
    except Exception as e:
        logger.error(f"Error generating form HTML: {str(e)}")
        return HttpResponse(
            f'<div class="alert alert-danger">Error generating form: {str(e)}</div>',
            status=500
        )

@login_required
@require_http_methods(["POST"])
def validate_form(request, entity_name: str) -> HttpResponse:
    """Validate form data with proper permissions."""
    try:
        data = json.loads(request.body)
        
        # Check permissions for each field
        for field_name, value in data.items():
            if not should_show_field(request.user, field_name, entity_name):
                return HttpResponse(
                    f'<div class="alert alert-danger">No permission to access field: {field_name}</div>',
                    status=403
                )
                
            if not can_edit_field(request.user, field_name, entity_name):
                return HttpResponse(
                    f'<div class="alert alert-danger">No permission to edit field: {field_name}</div>',
                    status=403
                )
        
        # Validate data
        schema = load_entity_schema(entity_name)
        errors = {}
        
        for field_name, value in data.items():
            field_schema = schema.get(field_name, {})
            
            # Required field validation
            if field_schema.get('required', False) and not value:
                errors[field_name] = 'This field is required'
                continue
                
            # Type validation
            field_type = field_schema.get('type', 'text')
            if field_type == 'number' and not str(value).isdigit():
                errors[field_name] = 'Must be a number'
                
        if errors:
            error_html = '<div class="alert alert-danger"><ul>'
            for field, error in errors.items():
                error_html += f'<li>{field}: {error}</li>'
            error_html += '</ul></div>'
            return HttpResponse(error_html, status=400)
            
        # Update properties
        upsert_entity_properties(entity_name, data)
        
        # Regenerate models
        regenerate_pydantic_models()
        
        return HttpResponse(
            '<div class="alert alert-success">Form submitted successfully!</div>'
        )
        
    except json.JSONDecodeError:
        return HttpResponse(
            '<div class="alert alert-danger">Invalid JSON data</div>',
            status=400
        )
    except Exception as e:
        logger.error(f"Error validating form: {str(e)}")
        return HttpResponse(
            f'<div class="alert alert-danger">Error validating form: {str(e)}</div>',
            status=500
        )

@login_required
@require_http_methods(["GET"])
def get_schema(request, entity_name: str) -> JsonResponse:
    """Get entity schema with proper permissions."""
    try:
        schema = load_entity_schema(entity_name)
        
        # Filter schema based on permissions
        filtered_schema = {}
        for field_name, field_schema in schema.items():
            if should_show_field(request.user, field_name, entity_name):
                filtered_schema[field_name] = field_schema
                
        return JsonResponse({
            'schema': filtered_schema,
            'permissions': get_field_permissions(request.user, entity_name),
            'watcher_status': get_watcher_status()
        })
        
    except Exception as e:
        logger.error(f"Error getting schema: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["POST"])
def validate_field(request, entity_name: str, field_name: str) -> HttpResponse:
    """Validate a single field with proper permissions."""
    try:
        if not should_show_field(request.user, field_name, entity_name):
            return HttpResponse(
                f'<div class="alert alert-danger">No permission to access field: {field_name}</div>',
                status=403
            )
            
        if not can_edit_field(request.user, field_name, entity_name):
            return HttpResponse(
                f'<div class="alert alert-danger">No permission to edit field: {field_name}</div>',
                status=403
            )
            
        data = json.loads(request.body)
        value = data.get('value')
        
        # Get field schema
        schema = load_entity_schema(entity_name)
        field_schema = schema.get(field_name, {})
        
        # Validate field
        if field_schema.get('required', False) and not value:
            return HttpResponse(
                f'<div class="alert alert-danger">This field is required</div>',
                status=400
            )
            
        # Type validation
        field_type = field_schema.get('type', 'text')
        if field_type == 'number' and not str(value).isdigit():
            return HttpResponse(
                f'<div class="alert alert-danger">Must be a number</div>',
                status=400
            )
            
        return HttpResponse(
            f'<div class="alert alert-success">Field is valid</div>'
        )
        
    except json.JSONDecodeError:
        return HttpResponse(
            f'<div class="alert alert-danger">Invalid JSON data</div>',
            status=400
        )
    except Exception as e:
        logger.error(f"Error validating field: {str(e)}")
        return HttpResponse(
            f'<div class="alert alert-danger">Error validating field: {str(e)}</div>',
            status=500
        ) 