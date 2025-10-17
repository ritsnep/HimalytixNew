from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from accounting.forms import JournalImportForm
from accounting.services.journal_import_service import JournalImportService
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

@method_decorator(require_POST, name='dispatch')
class JournalImportValidateView(View):
    """
    Handles the initial upload and validation of the journal import file.
    Caches the validated data for later processing.
    """
    def post(self, request, *args, **kwargs):
        form = JournalImportForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data['file']
            service = JournalImportService(request.organization, request.user)
            validation_result = service.validate_and_cache(file)

            if validation_result['is_valid']:
                return JsonResponse({
                    'success': True,
                    'message': _('File validated successfully. Ready for import.'),
                    'file_key': validation_result['file_key'],
                    'errors': validation_result['errors'] # Should be empty if valid
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': _('Validation failed.'),
                    'errors': validation_result['errors']
                })
        else:
            # Form is not valid (e.g., no file selected, wrong file type)
            errors = [{ 'row': 'Form', 'message': msg } for field, messages in form.errors.items() for msg in messages]
            return JsonResponse({'success': False, 'message': _('Invalid form submission.'), 'errors': errors})

@method_decorator(require_POST, name='dispatch')
class JournalImportProcessView(View):
    """
    Processes the cached, validated journal import data to create journal entries.
    """
    def post(self, request, *args, **kwargs):
        file_key = request.POST.get('file_key')
        if not file_key:
            return JsonResponse({'success': False, 'message': _('No file key provided for import.')})

        service = JournalImportService(request.organization, request.user)
        try:
            import_result = service.process_cached_import(file_key)
            if import_result['success']:
                return JsonResponse({
                    'success': True,
                    'message': _('Journal entries imported successfully.'),
                    'journal_ids': import_result['journal_ids']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': _('Errors occurred during import.'),
                    'errors': import_result['errors']
                })
        except Exception as e:
            logger.exception("Error processing cached journal import")
            return JsonResponse({'success': False, 'message': _('An unexpected error occurred during import.')})

class JournalImportView(View):
    template_name = 'accounting/journal_import.html'

    def get(self, request, *args, **kwargs):
        form = JournalImportForm()
        return render(request, self.template_name, {'form': form})