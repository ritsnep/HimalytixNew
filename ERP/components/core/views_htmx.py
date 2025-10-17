from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.generic import ListView

class HtmxTableMixin:
    """Mixin for HTMX-powered table views."""
    template_name = 'components/base/table_htmx.html'
    table_id = None
    page_size = 25
    columns = []
    bulk_actions = []
    row_actions = []
    export_formats = []
    filter_config = {}
    empty_message = None
    preserved_params = []

    def get_table_id(self) -> str:
        """Get unique ID for the table component."""
        return self.table_id or 'table-' + self.__class__.__name__.lower()

    def get_columns(self) -> list:
        """Get table column configurations."""
        return self.columns

    def get_bulk_actions(self) -> list:
        """Get bulk action configurations."""
        return self.bulk_actions

    def get_row_actions(self) -> list:
        """Get row action configurations."""
        return self.row_actions

    def get_export_formats(self) -> list:
        """Get export format configurations."""
        return self.export_formats

    def get_filter_config(self) -> dict:
        """Get filter configurations."""
        return self.filter_config

    def get_context_data(self, **kwargs):
        """Add table-specific context data."""
        context = super().get_context_data(**kwargs)
        context.update({
            'table_id': self.get_table_id(),
            'columns': self.get_columns(),
            'bulk_actions': self.get_bulk_actions(),
            'row_actions': self.get_row_actions(),
            'export_formats': self.get_export_formats(),
            'filter_config': self.get_filter_config(),
            'empty_message': self.empty_message,
            'preserved_params': self.preserved_params,
            'sort_by': self.request.GET.get('sort'),
            'sort_desc': self.request.GET.get('order') == 'desc',
        })
        return context

    def get_filterpanel_context(self, **kwargs):
        """Get context for the filter panel partial."""
        return {
            'filter_config': self.get_filter_config(),
            'request': self.request,
            'table_id': self.get_table_id(),
        }

    def render_to_response(self, context, **response_kwargs):
        """Handle both full page and HTMX partial responses."""
        is_htmx = self.request.headers.get('HX-Request') == 'true'
        
        if is_htmx:
            # For HTMX requests, return only the table component
            html = render_to_string(
                self.template_name,
                context=context,
                request=self.request
            )
            return HttpResponse(html)
            
        return super().render_to_response(context, **response_kwargs)

    def render_filterpanel_response(self, context):
        """Render filter panel partial."""
        template = 'components/base/table_filters.html'
        html = render_to_string(template, context=context, request=self.request)
        return HttpResponse(html)

    def handle_bulk_action(self, action: str, items: list) -> JsonResponse:
        """Handle bulk action requests."""
        handler = getattr(self, f'bulk_{action}', None)
        if not handler:
            return JsonResponse({
                'success': False,
                'message': f'Unknown action: {action}'
            }, status=400)

        try:
            result = handler(items)
            return JsonResponse({
                'success': True,
                'message': result.get('message', 'Operation completed successfully'),
                'reload': result.get('reload', True)
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)


class HtmxTableView(HtmxTableMixin, ListView):
    """Base view for HTMX-powered tables."""
    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Handle GET requests."""
        if request.headers.get('HX-Trigger') == 'showFilters':
            # Return filter panel partial
            context = self.get_filterpanel_context()
            return self.render_filterpanel_response(context)
            
        return super().get(request, *args, **kwargs)
