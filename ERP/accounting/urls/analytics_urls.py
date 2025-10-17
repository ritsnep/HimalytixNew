"""
Analytics URL Configuration - Phase 3 Task 8

Routes for analytics dashboard, financial analysis, and reporting endpoints.

URL Patterns:
    - analytics/ - Main dashboard
    - analytics/financial/ - Financial analysis
    - analytics/cash-flow/ - Cash flow dashboard
    - analytics/account/<id>/ - Individual account analysis
    - analytics/trends/ - Trend analysis
    - analytics/performance/ - Performance metrics
    - analytics/api/data/ - AJAX API for dynamic loading
    - analytics/export/ - Export reports
"""

from django.urls import path
from . import analytics_views

app_name = 'analytics'

urlpatterns = [
    # Main Dashboard
    path('', analytics_views.AnalyticsDashboardView.as_view(), name='dashboard'),
    
    # Financial Analysis
    path('financial/', analytics_views.FinancialAnalyticsView.as_view(), name='financial'),
    
    # Cash Flow Analysis
    path('cash-flow/', analytics_views.CashFlowAnalyticsView.as_view(), name='cash_flow'),
    
    # Individual Account Analysis
    path('account/<int:pk>/', analytics_views.AccountAnalyticsView.as_view(), name='account_analysis'),
    
    # Trend Analysis
    path('trends/', analytics_views.TrendAnalyticsView.as_view(), name='trends'),
    
    # Performance Metrics
    path('performance/', analytics_views.PerformanceAnalyticsView.as_view(), name='performance'),
    
    # AJAX API Endpoints
    path('api/data/', analytics_views.DashboardDataAPIView.as_view(), name='api_data'),
    
    # Export Analytics
    path('export/', analytics_views.AnalyticsExportView.as_view(), name='export'),
]
