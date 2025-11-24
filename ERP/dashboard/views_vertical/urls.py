# dashboard/views_vertical/urls.py
"""
URL Configuration for Vertical Dashboards HTML Pages

These are the user-facing dashboard pages (separate from API endpoints)
"""
from django.urls import path
from .html_views import vertical_dashboards_page

app_name = 'vertical_dashboards'

urlpatterns = [
    path('', vertical_dashboards_page, name='index'),
]
