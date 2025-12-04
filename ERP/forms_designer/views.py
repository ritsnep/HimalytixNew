from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Max
from django.core.exceptions import PermissionDenied, ValidationError

from rest_framework import viewsets, status as drf_status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounting.models import VoucherModeConfig, VoucherUDFConfig
from accounting.forms_factory import build_form
from .models import VoucherSchema, SchemaTemplate, VoucherSchemaStatus
from .serializers import (
    VoucherUDFConfigSerializer, VoucherSchemaSerializer,
    SchemaTemplateSerializer, VoucherModeConfigListSerializer
)
from .utils import get_active_schema, save_schema
from accounting.models import default_ui_schema
from .udf_extensions import (
    get_default_layout_config, get_default_visibility_rules,
    get_default_calculated_config, get_default_extended_validation
)

import json
import logging
import re
import difflib
from datetime import datetime

logger = logging.getLogger(__name__)

# Create your views here.


def _get_active_organization(request):
    """Resolve the user's active organization from request or session."""
    organization = getattr(request, "organization", None)
    if organization:
        return organization
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False) and hasattr(user, "get_active_organization"):
        organization = user.get_active_organization()
        if organization and hasattr(user, "set_active_organization"):
            user.set_active_organization(organization)
        return organization
    return None

@login_required
@permission_required('forms_designer.change_voucherschema', raise_exception=True)
def voucher_config_list(request):
    organization = _get_active_organization(request)
    if not organization:
        messages.warning(request, 'Please select an organization to continue.')
        return redirect('usermanagement:select_organization')

    configs = VoucherModeConfig.objects.filter(organization=organization)
    edit_id = request.GET.get('edit')
    edit_config = None
    schema = None
    schema_json = None
    udf_header = udf_line = None
    if edit_id:
        edit_config = get_object_or_404(VoucherModeConfig, config_id=edit_id, organization=organization)
        schema = get_active_schema(edit_config)
        # Convert dict-based schemas to lists and add 'name' property (robust for all sources)
        def dict_to_list_with_name(d):
            if not isinstance(d, dict):
                return []
            return [dict(field, name=key) if 'name' not in field else dict(field) for key, field in d.items()]
        if isinstance(schema.get('header'), dict):
            schema['header'] = dict_to_list_with_name(schema['header'])
        elif not isinstance(schema.get('header'), list):
            schema['header'] = []
        if isinstance(schema.get('lines'), dict):
            schema['lines'] = dict_to_list_with_name(schema['lines'])
        elif not isinstance(schema.get('lines'), list):
            schema['lines'] = []
        import json
        schema_json = json.dumps(schema)
        udf_qs = VoucherUDFConfig.objects.filter(voucher_mode=edit_config, is_active=True, archived_at__isnull=True)
        udf_header = list(udf_qs.filter(scope='header').order_by('display_order', 'field_name'))
        udf_line = list(udf_qs.filter(scope='line').order_by('display_order', 'field_name'))
        if request.method == 'POST':
            try:
                new_schema = json.loads(request.POST.get('schema_json', '{}'))
                save_schema(edit_config, new_schema, user=request.user)
                messages.success(request, 'Schema updated successfully!')
                if request.htmx:
                    return render(request, 'forms_designer/partials/config_modal_success.html', {'config': edit_config})
                return redirect(reverse('forms_designer:voucher_config_list'))
            except Exception as e:
                messages.error(request, f'Error saving schema: {e}')
    if request.htmx and edit_id:
        # Only return the form partial for modal AJAX requests
        return render(request, 'forms_designer/partials/config_modal_form.html', {
            'config': edit_config,
            'schema': schema,
            'schema_json': schema_json,
            'udf_header': udf_header,
            'udf_line': udf_line,
            'debug_modal': True,  # Add a debug flag for template
        })
    # Only return the full page for normal requests
    return render(request, 'forms_designer/voucher_config_list_modal.html', {
        'configs': configs,
        'edit_config': edit_config,
        'schema': schema,
        'schema_json': schema_json,
        'udf_header': udf_header,
        'udf_line': udf_line,
        'organization': organization,
    })

@login_required
@permission_required('forms_designer.view_voucherschema', raise_exception=True)
def schema_history(request, config_id):
    organization = _get_active_organization(request)
    if not organization:
        messages.warning(request, 'Please select an organization to continue.')
        return redirect('usermanagement:select_organization')
    config = get_object_or_404(VoucherModeConfig, config_id=config_id, organization=organization)
    schemas = VoucherSchema.objects.filter(voucher_mode_config=config).order_by('-version')
    return render(request, 'forms_designer/schema_history.html', {
        'config': config,
        'schemas': schemas,
    })

@login_required
@permission_required('forms_designer.change_voucherschema', raise_exception=True)
@require_POST
def toggle_voucher_config_status(request, config_id):
    organization = _get_active_organization(request)
    if not organization:
        return JsonResponse({'error': 'Active organization required.'}, status=400)
    config = get_object_or_404(VoucherModeConfig, config_id=config_id, organization=organization)
    if not request.user.has_perm('forms_designer.change_voucherschema'):
        return JsonResponse({'error': 'Permission denied.'}, status=403)
    # Toggle is_archived (active = not archived)
    config.is_archived = not config.is_archived
    config.save(update_fields=['is_archived'])
    # Optionally, handle is_default toggle here as well
    html = render_to_string('forms_designer/partials/voucher_config_status_cell.html', {'config': config, 'user': request.user})
    return JsonResponse({'html': html, 'is_archived': config.is_archived})

@login_required
@permission_required('forms_designer.change_voucherschema', raise_exception=True)
def designer(request, config_id):
    organization = _get_active_organization(request)
    if not organization:
        messages.warning(request, 'Please select an organization to continue.')
        return redirect('usermanagement:select_organization')
    config = get_object_or_404(VoucherModeConfig, config_id=config_id, organization=organization)
    schema = get_active_schema(config)
    
    # Fetch UDFs and split them by scope
    udf_qs = VoucherUDFConfig.objects.filter(voucher_mode=config, is_active=True, archived_at__isnull=True)
    udf_header = list(udf_qs.filter(scope='header').order_by('display_order', 'field_name'))
    udf_line = list(udf_qs.filter(scope='line').order_by('display_order', 'field_name'))

    # Convert schema to JSON for easy use in JavaScript
    schema_json = json.dumps(schema)

    return render(request, 'forms_designer/designer.html', {
        'config': config,
        'schema': schema,
        'schema_json': schema_json,
        'udf_header': udf_header,
        'udf_line': udf_line,
    })

@login_required
@permission_required('forms_designer.change_voucherschema', raise_exception=True)
def designer_v2(request, config_id):
    """Enhanced designer with modern UI and advanced features"""
    organization = _get_active_organization(request)
    if not organization:
        messages.warning(request, 'Please select an organization to continue.')
        return redirect('usermanagement:select_organization')
    config = get_object_or_404(VoucherModeConfig, config_id=config_id, organization=organization)
    schema = get_active_schema(config)
    
    # Ensure schema has proper structure
    if not isinstance(schema, dict):
        schema = {'header': [], 'lines': []}
    if 'header' not in schema:
        schema['header'] = []
    if 'lines' not in schema:
        schema['lines'] = []
    
    # Convert dict schemas to list format
    for section in ['header', 'lines']:
        if isinstance(schema[section], dict):
            schema[section] = [
                {**field, 'name': name} for name, field in schema[section].items()
            ]
    
    # If still empty after conversion, fall back to default_ui_schema for initial load
    if (not schema['header'] and not schema['lines']):
        try:
            base = default_ui_schema()
            if isinstance(base.get('header'), dict):
                schema['header'] = [
                    {**f, 'name': n} for n, f in base['header'].items()
                ]
            if isinstance(base.get('lines'), dict):
                schema['lines'] = [
                    {**f, 'name': n} for n, f in base['lines'].items()
                ]
        except Exception:
            # Keep empty if any error; UI will still function
            pass

    # Fetch UDFs and split them by scope
    udf_qs = VoucherUDFConfig.objects.filter(
        voucher_mode=config, 
        is_active=True, 
        archived_at__isnull=True
    )
    udf_header = list(udf_qs.filter(scope='header').order_by('display_order', 'field_name'))
    udf_line = list(udf_qs.filter(scope='line').order_by('display_order', 'field_name'))
    
    # Convert schema to JSON for JavaScript
    schema_json = json.dumps(schema)
    
    return render(request, 'forms_designer/designer_v2.html', {
        'config': config,
        'schema': schema,
        'schema_json': schema_json,
        'udf_header': udf_header,
        'udf_line': udf_line,
    })

@login_required
@permission_required('forms_designer.view_voucherschema', raise_exception=True)
def preview(request, config_id):
    organization = _get_active_organization(request)
    if not organization:
        messages.warning(request, 'Please select an organization to continue.')
        return redirect('usermanagement:select_organization')
    config = get_object_or_404(VoucherModeConfig, config_id=config_id, organization=organization)
    schema = get_active_schema(config)
    # --- UDFs: Add UDF fields to schema dynamically ---
    udf_qs = VoucherUDFConfig.objects.filter(voucher_mode=config, is_active=True, archived_at__isnull=True)
    for udf in udf_qs:
        # Only include valid Django form field arguments
        field_spec = {
            'type': udf.field_type if udf.field_type in ['char', 'text', 'date', 'decimal', 'number', 'select'] else 'char',
            'label': udf.display_name,
            'help_text': udf.help_text,
            'required': udf.is_required,
            'choices': None,
            'kwargs': {},
        }
        if udf.field_type == 'select':
            choices = udf.choices
            if choices and isinstance(choices, list):
                if choices and not isinstance(choices[0], (list, tuple)):
                    choices = [(c, c) for c in choices]
            field_spec['choices'] = choices
            field_spec['type'] = 'select'
        else:
            field_spec['choices'] = udf.choices if hasattr(udf, 'choices') else None
        # Remove any non-standard keys before passing to build_form
        clean_spec = {k: v for k, v in field_spec.items() if k in ['type', 'label', 'help_text', 'required', 'choices', 'kwargs']}
        # Place header UDFs in header, line UDFs in lines
        if udf.scope == 'header':
            if 'header' in schema and isinstance(schema['header'], dict):
                schema['header'][udf.field_name] = clean_spec
            elif 'header' in schema and isinstance(schema['header'], list):
                schema['header'].append({**clean_spec, 'name': udf.field_name})
        elif udf.scope == 'line':
            if 'lines' in schema and isinstance(schema['lines'], dict):
                schema['lines'][udf.field_name] = clean_spec
            elif 'lines' in schema and isinstance(schema['lines'], list):
                schema['lines'].append({**clean_spec, 'name': udf.field_name})
    # --- End UDF logic ---
    # Build the form for header (phase='header')
    organization = getattr(config, 'organization', None)
    header_schema = schema.get('header', {})
    if isinstance(header_schema, list):
        # Convert list of fields to a dictionary for build_form
        header_schema = {field.get('name'): field for field in header_schema if field.get('name')}

    form_class = build_form(header_schema, organization=organization, prefix='preview', phase='header')
    form = form_class()

    # Build the formset for lines (phase='line')
    line_schema = schema.get('lines', {})
    if isinstance(line_schema, list):
        # Convert list of fields to a dictionary for build_form
        line_schema = {field.get('name'): field for field in line_schema if field.get('name')}

    line_form_class = build_form(line_schema, organization=organization, prefix='preview_line', phase='line')
    from django.forms import formset_factory
    LineFormSet = formset_factory(line_form_class, extra=1) # Assuming 1 extra line for preview
    line_formset = LineFormSet()

    return render(request, 'forms_designer/preview_form.html', {
        'config': config,
        'form': form, # Header form
        'line_formset': line_formset, # Line formset
        'schema': schema,
    })

@require_POST
@login_required
@permission_required('forms_designer.change_voucherschema', raise_exception=True)
def save_schema_api(request, config_id):
    try:
        organization = _get_active_organization(request)
        if not organization:
            return JsonResponse({'status': 'error', 'message': 'Active organization required.'}, status=400)
        config = get_object_or_404(VoucherModeConfig, config_id=config_id, organization=organization)
        new_schema = json.loads(request.body)
        save_schema(config, new_schema, user=request.user)
        return JsonResponse({'status': 'success', 'message': 'Schema saved successfully.'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
