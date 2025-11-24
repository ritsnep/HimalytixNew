# dashboard/api/dashboard_urls.py
"""
Dashboard API URL Configuration

Provides REST API endpoints for vertical-specific dashboards
"""
from django.urls import path
from dashboard.views_vertical.views import (
    # Distributor endpoints
    distributor_dashboard,
    distributor_difot_trend,
    
    # Retailer endpoints
    retailer_dashboard,
    retailer_category_performance,
    
    # Manufacturer endpoints
    manufacturer_dashboard,
    manufacturer_oee_trend,
    
    # SaaS endpoints
    saas_dashboard,
    saas_mrr_trend,
    saas_cohort_analysis,
    
    # Service endpoints
    service_dashboard,
    
    # Unified endpoint
    unified_dashboard,
)

urlpatterns = [
    # ========================================================================
    # DISTRIBUTOR DASHBOARDS
    # ========================================================================
    path('distributor/', distributor_dashboard, name='api-dashboard-distributor'),
    path('distributor/difot-trend/', distributor_difot_trend, name='api-dashboard-distributor-difot-trend'),
    
    # ========================================================================
    # RETAILER DASHBOARDS
    # ========================================================================
    path('retailer/', retailer_dashboard, name='api-dashboard-retailer'),
    path('retailer/category-performance/', retailer_category_performance, name='api-dashboard-retailer-categories'),
    
    # ========================================================================
    # MANUFACTURER DASHBOARDS
    # ========================================================================
    path('manufacturer/', manufacturer_dashboard, name='api-dashboard-manufacturer'),
    path('manufacturer/oee-trend/', manufacturer_oee_trend, name='api-dashboard-manufacturer-oee-trend'),
    
    # ========================================================================
    # SAAS DASHBOARDS
    # ========================================================================
    path('saas/', saas_dashboard, name='api-dashboard-saas'),
    path('saas/mrr-trend/', saas_mrr_trend, name='api-dashboard-saas-mrr-trend'),
    path('saas/cohort/', saas_cohort_analysis, name='api-dashboard-saas-cohort'),
    
    # ========================================================================
    # SERVICE DASHBOARDS
    # ========================================================================
    path('service/', service_dashboard, name='api-dashboard-service'),
    
    # ========================================================================
    # UNIFIED DASHBOARD (All verticals)
    # ========================================================================
    path('unified/', unified_dashboard, name='api-dashboard-unified'),
]
