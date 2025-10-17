from django.db.models.query import QuerySet
from django.db.models import Q
from typing import Dict, List, Any
import operator

class DynamicFilter:
    """
    A reusable filter class that can be configured for any model.
    Allows dynamic filtering and sorting based on field configuration.
    """
    def __init__(self, queryset: QuerySet, config: Dict[str, Any]):
        """
        Initialize with a queryset and filter configuration.
        
        config format:
        {
            'filters': {
                'field_name': {
                    'type': 'exact|contains|gt|lt|...',
                    'value': filter_value
                }
            },
            'ordering': ['field1', '-field2'],  # Use - for descending order
            'search_fields': ['field1', 'field2']  # Fields to search in
        }
        """
        self.queryset = queryset
        self.config = config

    def apply_filters(self) -> QuerySet:
        """Apply configured filters to queryset"""
        filters = self.config.get('filters', {})
        q_objects = []
        
        for field, filter_config in filters.items():
            if 'value' not in filter_config or not filter_config['value']:
                continue
                
            filter_type = filter_config.get('type', 'exact')
            lookup = f"{field}__{filter_type}"
            q_objects.append(Q(**{lookup: filter_config['value']}))
        
        if q_objects:
            return self.queryset.filter(operator.and_(*q_objects))
        return self.queryset

    def apply_search(self, search_term: str = None) -> QuerySet:
        """Apply search across configured search fields"""
        if not search_term:
            return self.queryset
            
        search_fields = self.config.get('search_fields', [])
        if not search_fields:
            return self.queryset
            
        q_objects = []
        for field in search_fields:
            q_objects.append(Q(**{f"{field}__icontains": search_term}))
            
        if q_objects:
            return self.queryset.filter(operator.or_(*q_objects))
        return self.queryset

    def apply_ordering(self) -> QuerySet:
        """Apply configured ordering"""
        ordering = self.config.get('ordering', [])
        if ordering:
            return self.queryset.order_by(*ordering)
        return self.queryset

    def get_filtered_queryset(self, search_term: str = None) -> QuerySet:
        """Apply all filters and return final queryset"""
        qs = self.apply_filters()
        qs = self.apply_search(search_term)
        qs = self.apply_ordering()
        return qs

class ReportData:
    """
    A class to handle report data preparation with filtering, sorting,
    and export capabilities.
    """
    def __init__(self, queryset: QuerySet, config: Dict[str, Any]):
        self.queryset = queryset
        self.config = config
        self.filter = DynamicFilter(queryset, config)
        
    def get_data(self, search_term: str = None) -> QuerySet:
        """Get filtered and sorted data"""
        return self.filter.get_filtered_queryset(search_term)
        
    def get_export_data(self, format: str = 'csv') -> List[Dict]:
        """
        Export data in specified format
        Currently supports: csv, excel, json
        """
        data = self.get_data()
        # Convert queryset to list of dicts
        fields = self.config.get('export_fields', [])
        if not fields:
            return list(data.values())
        return list(data.values(*fields))
