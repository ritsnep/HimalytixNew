from django.shortcuts import get_object_or_404, render
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from accounting.services.validation import JournalValidationService
import json

from accounting.models import Journal
from accounting.forms import JournalForm, JournalLineFormSet
from accounting.views.views_mixins import UserOrganizationMixin
from utils.htmx import require_htmx

class JournalCheckView(UserOrganizationMixin, View):
    template_name = "accounting/partials/journal_check_panel.html"

    @method_decorator(require_htmx)
    def post(self, request, *args, **kwargs):
        try:
            if request.content_type == 'application/json':
                return self._handle_json_request(request)
            return self._handle_form_request(request, **kwargs)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'is_valid': False,
                'errors': ['Invalid JSON data']
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'is_valid': False,
                'errors': [str(e)]
            }, status=500)

    def _handle_json_request(self, request):
        data = json.loads(request.body)
        journal_data = data.get('journal')
        lines_data = data.get('lines', [])
        
        journal_instance = Journal(
            date=journal_data.get('date'),
            description=journal_data.get('description'),
            organization=self.get_organization()
        )
        
        form = JournalForm(data=journal_data, instance=journal_instance)
        formset = JournalLineFormSet(data=lines_data)
        
        validator = JournalValidationService(
            journal=journal_instance,
            form=form,
            formset=formset,
            organization=self.get_organization()
        )
        
        errors = validator.validate_journal_entry()
        
        return JsonResponse({
            'is_valid': len(errors) == 0,
            'errors': errors
        })

    def _handle_form_request(self, request, **kwargs):
        journal = get_object_or_404(
            Journal, 
            pk=kwargs.get('pk'), 
            organization=self.get_organization()
        )
        
        form = JournalForm(
            request.POST, 
            instance=journal, 
            organization=self.get_organization()
        )
        formset = JournalLineFormSet(
            request.POST, 
            instance=journal, 
            prefix='lines', 
            form_kwargs={'organization': self.get_organization()}
        )

        validator = JournalValidationService(
            journal=journal,
            form=form,
            formset=formset,
            organization=self.get_organization()
        )

        validation_errors = validator.validate_journal_entry()

        context = {
            'form': form,
            'formset': formset,
            'journal': journal,
            'validation_errors': validation_errors
        }
        return render(request, self.template_name, context)