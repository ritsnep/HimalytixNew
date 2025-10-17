from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from django.db.models import Q, QuerySet
from django.http import HttpRequest


@dataclass
class ColumnConfig:
    """Configuration for a table column."""
    name: str 
    label: str
    sortable: bool = True
    filterable: bool = True
    visible: bool = True
    template: Optional[str] = None
    css_classes: Optional[List[str]] = None
    format_func: Optional[callable] = None


class DynamicFilter:
    """Base class for dynamic query filters."""
    def __init__(self, name: str, field: str, label: str):
        self.name = name
        self.field = field
        self.label = label
        
    def apply(self, queryset: QuerySet, value: Any) -> QuerySet:
        """Apply the filter to the queryset."""
        raise NotImplementedError


class TextFilter(DynamicFilter):
    """Text-based filter supporting contains, startswith, etc."""
    def __init__(self, name: str, field: str, label: str, lookup: str = 'icontains'):
        super().__init__(name, field, label)
        self.lookup = lookup
        
    def apply(self, queryset: QuerySet, value: str) -> QuerySet:
        if value:
            return queryset.filter(**{f"{self.field}__{self.lookup}": value})
        return queryset


class ChoiceFilter(DynamicFilter):
    """Filter for choice fields."""
    def __init__(self, name: str, field: str, label: str, choices: List[Tuple]):
        super().__init__(name, field, label)
        self.choices = choices
        
    def apply(self, queryset: QuerySet, value: Any) -> QuerySet:
        if value:
            return queryset.filter(**{self.field: value})
        return queryset


class ReportData:
    """Class to manage report data and filtering."""
    def __init__(self, queryset: QuerySet, columns: List[ColumnConfig]):
        self.base_queryset = queryset
        self.columns = columns
        self.filters: List[DynamicFilter] = []
        self.search_fields: List[str] = []
        
    def add_filter(self, filter_obj: DynamicFilter):
        """Add a filter to the report."""
        self.filters.append(filter_obj)
        
    def set_search_fields(self, fields: List[str]):
        """Set fields to be used in global search."""
        self.search_fields = fields
        
    def apply_filters(self, filter_values: Dict[str, Any]) -> QuerySet:
        """Apply all active filters to the queryset."""
        queryset = self.base_queryset
        
        for filter_obj in self.filters:
            if filter_obj.name in filter_values:
                queryset = filter_obj.apply(queryset, filter_values[filter_obj.name])
                
        return queryset
        
    def apply_search(self, search_term: str) -> QuerySet:
        """Apply global search across specified fields."""
        if not search_term or not self.search_fields:
            return self.base_queryset
            
        q_objects = Q()
        for field in self.search_fields:
            q_objects |= Q(**{f"{field}__icontains": search_term})
            
        return self.base_queryset.filter(q_objects)
        
    def get_data(self, request: HttpRequest) -> QuerySet:
        """Get filtered and sorted data."""
        queryset = self.base_queryset
        
        # Apply filters
        filter_values = {
            f.name: request.GET.get(f.name)
            for f in self.filters
        }
        queryset = self.apply_filters(filter_values)
        
        # Apply search
        search_term = request.GET.get('search')
        if search_term:
            queryset = self.apply_search(search_term)
            
        # Apply sorting
        sort_field = request.GET.get('sort')
        if sort_field:
            sort_desc = request.GET.get('desc', '').lower() == 'true'
            sort_field = f"-{sort_field}" if sort_desc else sort_field
            queryset = queryset.order_by(sort_field)
            
        return queryset
