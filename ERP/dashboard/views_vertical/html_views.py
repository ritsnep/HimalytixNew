# dashboard/views_vertical/html_views.py
"""
HTML Views for Vertical Dashboards

Serves the interactive HTML dashboard pages (separate from main dashboard)
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def vertical_dashboards_page(request):
    """
    Render the interactive vertical dashboards page
    
    This is accessible from the sidebar as a separate dashboard
    from the main ERP dashboard.
    """
    return render(request, 'dashboard/vertical_dashboards.html', {
        'page_title': 'Vertical Dashboards',
        'sidebar_active': 'vertical-dashboards'
    })
