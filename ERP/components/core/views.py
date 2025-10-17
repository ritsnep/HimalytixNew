from typing import Any, Dict, List, Optional, Type, Union

from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.forms import Form
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.response import TemplateResponse

from components.core.forms import DynamicForm, DynamicModelForm
from components.core.reports import ReportData


class DynamicFormViewMixin:
    """Mixin for views that handle dynamic forms."""
    form_class: Type[Union[DynamicForm, DynamicModelForm]] = None
    template_name: str = None
    success_url: str = None
    
    def get_form_class(self):
        """Get the form class to use."""
        if self.form_class is None:
            raise ImproperlyConfigured("Form class not specified.")
        return self.form_class
        
    def get_form_kwargs(self) -> Dict[str, Any]:
        """Get the keyword arguments for instantiating the form."""
        kwargs = {
            'initial': self.get_initial(),
            'prefix': self.get_prefix(),
        }
        
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.request.POST,
                'files': self.request.FILES,
            })
            
        # Add field configuration if available
        field_config = self.get_field_config()
        if field_config:
            kwargs['field_config'] = field_config
            
        return kwargs
        
    def get_field_config(self) -> Optional[Dict]:
        """Get field configuration for the form."""
        return getattr(self, 'field_config', None)
        
    def get_initial(self) -> Dict:
        """Get initial data for the form."""
        return {}
        
    def get_prefix(self) -> Optional[str]:
        """Get form prefix."""
        return None
        
    def form_valid(self, form: Form) -> HttpResponse:
        """Handle valid form data."""
        return HttpResponse()
        
    def form_invalid(self, form: Form) -> HttpResponse:
        """Handle invalid form data."""
        return HttpResponse()


class DynamicTableMixin:
    """Mixin for views that display dynamic tables/reports."""
    report_class: Type[ReportData] = None
    template_name: str = None
    
    def get_report_data(self) -> ReportData:
        """Get the report data instance."""
        if self.report_class is None:
            raise ImproperlyConfigured("Report class not specified.")
            
        report = self.report_class(
            queryset=self.get_queryset(),
            columns=self.get_columns()
        )
        
        # Configure filters if available
        filters = self.get_filters()
        if filters:
            for filter_obj in filters:
                report.add_filter(filter_obj)
                
        # Configure search if available
        search_fields = self.get_search_fields()
        if search_fields:
            report.set_search_fields(search_fields)
            
        return report
        
    def get_queryset(self):
        """Get the base queryset for the report."""
        raise NotImplementedError
        
    def get_columns(self):
        """Get the column configurations for the report."""
        raise NotImplementedError
        
    def get_filters(self):
        """Get filter configurations for the report."""
        return []
        
    def get_search_fields(self):
        """Get fields to be included in global search."""
        return []
        
    def get_context_data(self, **kwargs):
        """Get context data for the template."""
        context = super().get_context_data(**kwargs)
        report = self.get_report_data()
        context.update({
            'report': report,
            'data': report.get_data(self.request)
        })
        return context


class DialogViewMixin:
    """Mixin for views that handle dialog boxes."""
    dialog_template_name: str = None
    dialog_context_name: str = 'dialog'
    
    def get_dialog_template_name(self) -> str:
        """Get the template name for the dialog."""
        if self.dialog_template_name is None:
            raise ImproperlyConfigured("Dialog template name not specified.")
        return self.dialog_template_name
        
    def get_dialog_context_data(self, **kwargs) -> Dict[str, Any]:
        """Get extra context data for the dialog."""
        return {}
        
    def render_dialog_to_response(self, **kwargs) -> HttpResponse:
        """Render the dialog template with context."""
        context = self.get_dialog_context_data(**kwargs)
        return TemplateResponse(
            request=self.request,
            template=self.get_dialog_template_name(),
            context=context
        )
        
    def ajax_dialog_success(self, **kwargs) -> JsonResponse:
        """Return success response for AJAX dialog submission."""
        return JsonResponse({
            'status': 'success',
            'message': kwargs.get('message', 'Operation successful'),
            'redirect_url': kwargs.get('redirect_url')
        })
        
    def ajax_dialog_error(self, **kwargs) -> JsonResponse:
        """Return error response for AJAX dialog submission."""
        return JsonResponse({
            'status': 'error',
            'message': kwargs.get('message', 'Operation failed'),
            'errors': kwargs.get('errors', {}),
        }, status=400)
