"""
Import/Export Views - Phase 3 Task 3

Views for batch import/export operations:
- ImportListView: List import history
- ImportCreateView: Create new import
- ImportStatusView: Check import status
- ExportView: Export journals
"""

import logging

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView

from accounting.services.import_export_service import (
    ImportService,
    ExportService,
    ImportTemplate,
    DuplicateDetector
)
from accounting.models import Journal
from usermanagement.mixins import UserOrganizationMixin
from utils.file_uploads import (
    ALLOWED_IMPORT_EXTENSIONS,
    MAX_IMPORT_UPLOAD_BYTES,
    iter_validated_files,
)

logger = logging.getLogger(__name__)


class ImportListView(UserOrganizationMixin, ListView):
    """List import history and status."""
    
    template_name = 'accounting/import_export/import_list.html'
    context_object_name = 'imports'
    paginate_by = 20
    
    def get_queryset(self):
        """Get user's imports."""
        # Return recent journals created via import
        return Journal.objects.filter(
            organization=self.organization,
            status='Draft'  # Recently imported journals are draft
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add import statistics."""
        context = super().get_context_data(**kwargs)
        
        context['import_stats'] = {
            'total_imports': Journal.objects.filter(
                organization=self.organization
            ).count(),
            'draft_imports': Journal.objects.filter(
                organization=self.organization,
                status='Draft'
            ).count(),
            'posted_imports': Journal.objects.filter(
                organization=self.organization,
                status='Posted'
            ).count(),
        }
        
        return context


class ImportCreateView(UserOrganizationMixin, View):
    """Handle import file upload and processing."""
    
    template_name = 'accounting/import_export/import_create.html'
    
    def get(self, request):
        """Display import form."""
        context = {
            'import_types': [
                {'id': 'excel', 'name': 'Excel (.xlsx)', 'icon': 'fas fa-file-excel'},
                {'id': 'csv', 'name': 'CSV (.csv)', 'icon': 'fas fa-file-csv'},
            ],
            'download_template_url': '#'  # URL to download template
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Process uploaded file."""
        try:
            file = request.FILES.get('file')
            import_type = request.POST.get('import_type', 'excel')
            skip_duplicates = request.POST.get('skip_duplicates', 'on') == 'on'
            
            if not file:
                return JsonResponse({'error': _('No file uploaded')}, status=400)
            
            # Create import service
            service = ImportService(self.organization, request.user)

            try:
                cleaned_file = self._prepare_import_file(file, import_type)
            except ValidationError as exc:
                return JsonResponse({'error': str(exc)}, status=400)
            
            # Process file based on type
            if import_type == 'excel':
                cleaned_file.seek(0)
                result = service.import_excel(cleaned_file, skip_duplicates)
            elif import_type == 'csv':
                file_content = cleaned_file.read().decode('utf-8')
                result = service.import_csv(file_content, skip_duplicates)
            else:
                return JsonResponse({'error': _('Invalid import type')}, status=400)
            
            logger.info(f"Import completed: {result['imported_count']} journals")
            
            return JsonResponse(result)
        
        except Exception as e:
            logger.exception(f"Import error: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def _prepare_import_file(self, uploaded_file, import_type: str):
        """Validate uploaded import files (optionally zipped) and return a single file handle."""
        if import_type not in {'excel', 'csv'}:
            raise ValidationError(_('Invalid import type'))

        allowed_extensions = ALLOWED_IMPORT_EXTENSIONS if import_type == 'excel' else {'.csv'}
        label = str(_('Journal import file'))
        files = list(
            iter_validated_files(
                uploaded_file,
                allowed_extensions=allowed_extensions,
                max_bytes=MAX_IMPORT_UPLOAD_BYTES,
                allow_archive=True,
                max_members=1,
                label=label,
            )
        )

        if not files:
            raise ValidationError(_('Uploaded file is empty.'))

        return files[0][1]


class DownloadTemplateView(UserOrganizationMixin, View):
    """Download Excel template for import."""
    
    def get(self, request):
        """Download import template."""
        try:
            buffer = ImportTemplate.create_excel_template(self.organization)
            
            response = HttpResponse(
                buffer.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="journal_import_template.xlsx"'
            
            logger.info(f"Template downloaded for {self.organization}")
            return response
        
        except Exception as e:
            logger.exception(f"Template download error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class ExportView(UserOrganizationMixin, View):
    """Export journals to various formats."""
    
    def post(self, request):
        """Export journals."""
        try:
            export_format = request.POST.get('format', 'excel')
            filters = request.POST.get('filters', '{}')
            
            # Get journals to export
            journals = Journal.objects.filter(
                organization=self.organization,
                status='Posted'
            ).order_by('-date')[:100]  # Limit to 100
            
            if export_format == 'excel':
                buffer, filename = ExportService.export_journals_to_excel(journals)
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif export_format == 'csv':
                buffer, filename = ExportService.export_journals_to_csv(journals)
                content_type = 'text/csv'
            else:
                return JsonResponse({'error': _('Invalid export format')}, status=400)
            
            response = HttpResponse(buffer.getvalue(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            logger.info(f"Exported {journals.count()} journals as {export_format}")
            return response
        
        except Exception as e:
            logger.exception(f"Export error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class ImportStatusView(UserOrganizationMixin, View):
    """Check import status."""
    
    def get(self, request, import_id):
        """Get import status."""
        try:
            # Retrieve import status (in real implementation, store in DB)
            status = {
                'import_id': import_id,
                'status': 'completed',
                'progress': 100,
                'imported': 50,
                'skipped': 5,
                'duplicates': 2,
                'errors': []
            }
            
            return JsonResponse(status)
        
        except Exception as e:
            logger.exception(f"Status check error: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class BulkActionView(UserOrganizationMixin, View):
    """Perform bulk actions on imported journals."""
    
    def post(self, request):
        """Perform bulk action."""
        try:
            action = request.POST.get('action')
            journal_ids = request.POST.getlist('journal_ids[]')
            
            journals = Journal.objects.filter(
                organization=self.organization,
                id__in=journal_ids
            )
            
            if action == 'post':
                for journal in journals:
                    if journal.status == 'Draft':
                        journal.status = 'Posted'
                        journal.save()
            
            elif action == 'delete':
                journals.delete()
            
            elif action == 'validate':
                errors = []
                for journal in journals:
                    # Validate each journal
                    pass
            
            logger.info(f"Bulk action '{action}' on {journals.count()} journals")
            
            return JsonResponse({
                'success': True,
                'message': f'{journals.count()} journals updated'
            })
        
        except Exception as e:
            logger.exception(f"Bulk action error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
