# dashboard/views_vertical/__init__.py
"""
Vertical Dashboard Views Package

Separate from the main dashboard, this package provides
industry-specific KPI dashboards accessible from the sidebar.
"""

from .views import (
    # Distributor views
    distributor_dashboard,
    distributor_difot_trend,
    
    # Retailer views
    retailer_dashboard,
    retailer_category_performance,
    
    # Manufacturer views
    manufacturer_dashboard,
    manufacturer_oee_trend,
    
    # SaaS views
    saas_dashboard,
    saas_mrr_trend,
    saas_cohort_analysis,
    
    # Service views
    service_dashboard,
    
    # Unified view
    unified_dashboard,
)

__all__ = [
    'distributor_dashboard',
    'distributor_difot_trend',
    'retailer_dashboard',
    'retailer_category_performance',
    'manufacturer_dashboard',
    'manufacturer_oee_trend',
    'saas_dashboard',
    'saas_mrr_trend',
    'saas_cohort_analysis',
    'service_dashboard',
    'unified_dashboard',
]
