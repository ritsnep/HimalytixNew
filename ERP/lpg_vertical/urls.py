from django.urls import path

from . import views

app_name = "lpg_vertical"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("api/dashboard-summary/", views.api_dashboard_summary, name="api_dashboard_summary"),
    path("api/noc-purchases/", views.api_recent_noc_purchases, name="api_recent_noc_purchases"),
    path("api/logistics/", views.api_recent_logistics, name="api_recent_logistics"),
]
