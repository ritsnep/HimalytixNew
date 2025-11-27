"""
Universal Bulk Import and Template System
Dynamically handles bulk import and demo templates for any model
"""
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db import transaction
from django.utils.decorators import method_decorator
from django.urls import reverse
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class BulkImportMixin:
    model = None
    bulk_fields: List[str] = []
    bulk_field_config: Dict[str, Dict[str, Any]] = {}
    custom_validator_method: Optional[str] = None
    auto_fields: List[str] = []

    def get_bulk_fields(self) -> List[str]:
        if not self.bulk_fields:
            raise NotImplementedError("bulk_fields must be defined")
        return self.bulk_fields

    def get_field_config(self, field_name: str) -> Dict[str, Any]:
        return self.bulk_field_config.get(field_name, {})

    def parse_bulk_data(self, bulk_data: str, organization) -> List[Dict[str, Any]]:
        results = []
        lines = bulk_data.strip().split('\n')
        fields = self.get_bulk_fields()
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in (line.split('\t') if '\t' in line else line.split(','))]
            row_data = {'line_num': line_num, 'organization': organization}
            for i, field_name in enumerate(fields):
                value = parts[i] if i < len(parts) else ''
                field_config = self.get_field_config(field_name)
                field_type = field_config.get('type', 'str')
                if field_type == 'bool':
                    value = str(value).lower() in ('true', '1', 'yes', 'active')
                elif field_type == 'int':
                    value = int(value) if value else None
                elif field_type == 'float':
                    value = float(value) if value else None
                elif field_type == 'decimal':
                    from decimal import Decimal
                    value = Decimal(value) if value else None
                row_data[field_name] = value
            results.append(row_data)
        return results

    def validate_row(self, row_data: Dict[str, Any], organization):
        errors = []
        prepared_data = {'organization': organization}
        fields = self.get_bulk_fields()
        existing = None
        for field_name in fields:
            field_config = self.get_field_config(field_name)
            value = row_data.get(field_name)
            if field_config.get('required', False) and not value:
                errors.append(f'{field_name} is required')
                continue
            if field_config.get('type') == 'fk':
                fk_model = field_config.get('model')
                fk_lookup = field_config.get('lookup', 'name')
                fk_filter = {fk_lookup: value}
                if hasattr(fk_model, 'organization'):
                    fk_filter['organization'] = organization
                fk_instance = fk_model.objects.filter(**fk_filter).first() if value else None
                if not fk_instance and value:
                    errors.append(f'{field_name}: {value} not found')
                prepared_data[field_name] = fk_instance
            elif field_config.get('type') == 'self':
                if value:
                    lookup_field = field_config.get('lookup', 'code')
                    parent = self.model.objects.filter(organization=organization, **{lookup_field: value}).first()
                    if not parent:
                        errors.append(f'Parent {value} not found')
                    prepared_data[field_name] = parent
                else:
                    prepared_data[field_name] = None
            elif field_config.get('type') == 'choice':
                choices = field_config.get('choices', [])
                if value and value not in [c[0] for c in choices]:
                    valid_choices = ', '.join([c[0] for c in choices])
                    errors.append(f'{field_name}: invalid choice. Valid: {valid_choices}')
                else:
                    prepared_data[field_name] = value
            else:
                prepared_data[field_name] = value
        if self.custom_validator_method and hasattr(self, self.custom_validator_method):
            validator = getattr(self, self.custom_validator_method)
            custom_errors = validator(prepared_data, row_data) or []
            errors.extend(custom_errors)
        is_valid = len(errors) == 0
        return is_valid, errors, prepared_data, existing

    def validate_all_rows(self, results: List[Dict], organization, update_existing: bool = False) -> List[Dict]:
        validated = []
        for row_data in results:
            is_valid, errors, prepared_data, existing = self.validate_row(row_data, organization)
            validated.append({
                'line_num': row_data.get('line_num'),
                'row_data': row_data,
                'prepared_data': prepared_data,
                'valid': is_valid,
                'errors': errors,
                'existing': existing,
            })
        return validated

    def save_validated_rows(self, validated_results: List[Dict], update_existing: bool = False, skip_errors: bool = False):
        saved_count = 0
        error_count = 0
        with transaction.atomic():
            for result in validated_results:
                if result['valid']:
                    try:
                        prepared_data = result['prepared_data']
                        instance = self.model.objects.create(**prepared_data)
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"Error saving {self.model.__name__}: {e}")
                        result['valid'] = False
                        result['errors'].append(str(e))
                        error_count += 1
                        if not skip_errors:
                            raise
                else:
                    error_count += 1
        return saved_count, error_count


class DemoTemplateMixin:
    model = None
    demo_templates: Dict[str, List[Dict[str, Any]]] = {}
    template_metadata: Dict[str, Dict[str, str]] = {}

    def get_demo_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        return getattr(self, 'demo_templates', {}) or {}

    def get_template_metadata(self, template_key: str) -> Dict[str, str]:
        metadata = self.template_metadata.get(template_key, {})
        if not metadata:
            metadata = {
                'name': template_key.replace('_', ' ').replace('-', ' ').title(),
                'description': f'{template_key.title()} template for {self.model.__name__}',
            }
        return metadata

    def resolve_foreign_keys(self, record_data: Dict, organization) -> Dict:
        resolved_data = record_data.copy()
        model_fields = {f.name: f for f in self.model._meta.get_fields()}
        for field_name, value in record_data.items():
            field = model_fields.get(field_name)
            if field and getattr(field, 'many_to_one', False) and isinstance(value, str):
                related_model = field.related_model
                fk_filter = {}
                if hasattr(related_model, 'name'):
                    fk_filter['name'] = value
                elif hasattr(related_model, 'code'):
                    fk_filter['code'] = value
                else:
                    continue
                if hasattr(related_model, 'organization'):
                    fk_filter['organization'] = organization
                related_obj = related_model.objects.filter(**fk_filter).first()
                if related_obj:
                    resolved_data[field_name] = related_obj
                else:
                    resolved_data.pop(field_name, None)
        return resolved_data

    def import_template(self, template_key: str, organization):
        templates = self.get_demo_templates()
        if template_key not in templates:
            return 0, [f'Template {template_key} not found']
        template_data = templates[template_key]
        validated_records = []
        errors = []
        for i, record_data in enumerate(template_data, 1):
            try:
                record_data['organization'] = organization
                record_data = self.resolve_foreign_keys(record_data, organization)
                validated_records.append(record_data)
            except Exception as e:
                errors.append(f'Record {i}: {str(e)}')
        if errors:
            return 0, errors
        created_count = 0
        try:
            with transaction.atomic():
                for record_data in validated_records:
                    self.model.objects.create(**record_data)
                    created_count += 1
        except Exception as e:
            logger.error(f"Template import failed: {e}")
            return 0, [str(e)]
        return created_count, []


class UniversalBulkImportView(BulkImportMixin, View):
    def post(self, request, *args, **kwargs):
        bulk_data = request.POST.get('bulk_data', '').strip()
        skip_errors = request.POST.get('skip_errors') == 'on'
        update_existing = request.POST.get('update_existing') == 'on'
        validate_only = request.POST.get('validate_only') == 'on'
        if not bulk_data:
            return HttpResponse('<div class="alert alert-warning">No data provided.</div>')
        organization = self.get_organization()
        if not organization:
            return HttpResponse('<div class="alert alert-danger">No organization found.</div>')
        results = self.parse_bulk_data(bulk_data, organization)
        validated_results = self.validate_all_rows(results, organization, update_existing)
        saved_count = 0
        error_count = 0
        if not validate_only:
            saved_count, error_count = self.save_validated_rows(validated_results, update_existing=update_existing, skip_errors=skip_errors)
        context = {
            'results': validated_results,
            'saved_count': saved_count,
            'error_count': error_count,
            'total_count': len(validated_results),
            'validate_only': validate_only,
            'model_name': self.model.__name__,
            'fields': self.get_bulk_fields(),
        }
        template_name = getattr(self, 'preview_template', 'accounting/partials/bulk_import_preview.html')
        html = render_to_string(template_name, context, request=request)
        return HttpResponse(html)


class UniversalDemoImportView(DemoTemplateMixin, View):
    def post(self, request, *args, **kwargs):
        template_key = request.POST.get('template_type')
        organization = self.get_organization()
        if not organization:
            return HttpResponse('<div class="alert alert-danger">No organization found.</div>')
        created_count, errors = self.import_template(template_key, organization)
        if errors:
            error_html = '<br>'.join(errors)
            return HttpResponse(f'<div class="alert alert-danger"><strong>Import Failed:</strong><br>{error_html}</div>')
        metadata = self.get_template_metadata(template_key)
        list_url = self.get_list_url()
        html = f'''<div class="alert alert-success">
            <h5><i class="bx bx-check-circle"></i> Success!</h5>
            <p>Successfully imported <strong>{created_count}</strong> records from <strong>{metadata["name"]}</strong> template.</p>
            <a href="{list_url}" class="btn btn-sm btn-success mt-2">
                <i class="bx bx-list-ul"></i> View {self.model._meta.verbose_name_plural.title()}
            </a>
        </div>'''
        return HttpResponse(html)

    def get(self, request, *args, **kwargs):
        template_key = request.GET.get('template')
        templates = self.get_demo_templates()
        if template_key not in templates:
            return HttpResponse('<div class="alert alert-warning">Template not found.</div>')
        template_data = templates[template_key]
        metadata = self.get_template_metadata(template_key)
        context = {
            'template_key': template_key,
            'template_metadata': metadata,
            'template_data': template_data,
            'model_name': self.model.__name__,
        }
        template_name = getattr(self, 'preview_template', 'accounting/partials/demo_template_preview.html')
        html = render_to_string(template_name, context, request=request)
        return HttpResponse(html)

    def get_list_url(self) -> str:
        app_label = self.model._meta.app_label
        model_name = self.model._meta.model_name
        try:
            return reverse(f'{app_label}:{model_name}_list')
        except Exception:
            return '/'
