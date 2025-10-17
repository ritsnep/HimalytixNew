"""Base view mixins for handling dynamic components"""
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.http import JsonResponse
from .reports import ReportData

class DynamicFormViewMixin:
    """Mixin for views that use dynamic forms"""
    field_config = {}

    def get_form_kwargs(self):
        """Add field configuration to form kwargs"""
        kwargs = super().get_form_kwargs()
        kwargs['field_config'] = self.get_field_config()
        return kwargs
    
    def get_field_config(self):
        """Get field configuration - override to make dynamic"""
        return self.field_config

class DynamicTableMixin:
    """Mixin for views that display data in tables with sorting/filtering"""
    filter_config = {
        'filters': {},
        'ordering': [],
        'search_fields': []
    }
    
    def get_filter_config(self):
        """Get filter configuration - override to make dynamic"""
        return self.filter_config
        
    def get_queryset(self):
        """Get filtered queryset"""
        qs = super().get_queryset()
        report_data = ReportData(qs, self.get_filter_config())
        return report_data.get_data(self.request.GET.get('search'))
        
    def get_context_data(self, **kwargs):
        """Add filter configuration to context"""
        context = super().get_context_data(**kwargs)
        context['filter_config'] = self.get_filter_config()
        return context

class DialogViewMixin:
    """Mixin for views that render in dialog boxes"""
    template_name_dialog = None
    
    def get_template_names(self):
        """Get dialog template if requested via AJAX"""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return [self.template_name_dialog]
        return super().get_template_names()

class AjaxResponseMixin:
    """Mixin to handle AJAX responses"""
    def form_valid(self, form):
        """Return JSON response for AJAX requests"""
        response = super().form_valid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'redirect_url': self.get_success_url()
            })
        return response
        
    def form_invalid(self, form):
        """Return JSON response for AJAX requests"""
        response = super().form_invalid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            })
        return response
