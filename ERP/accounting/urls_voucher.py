"""
Voucher URL Configuration - Phase 1 Standardized URLs

This module defines the standardized URL patterns for the voucher/journal entry system.
These URLs replace the fragmented patterns previously scattered across the codebase.

Pattern:
  - /journal/ - Base path for all journal operations
  - /journal/list - List all journals
  - /journal/create - Create new journal
  - /journal/<id> - View journal details
  - /journal/<id>/edit - Edit journal
  - /journal/<id>/post - Post journal
  - /journal/htmx/ - HTMX handlers for dynamic interactions
"""

from django.urls import path
from accounting.views.voucher_create_view import VoucherCreateView
from accounting.views.voucher_list_view import VoucherListView
from accounting.views.voucher_detail_view import VoucherDetailView
from accounting.views.voucher_edit_view import VoucherEditView
from accounting.views.voucher_htmx_handler import VoucherHtmxHandler

app_name = 'accounting_voucher'

urlpatterns = [
    # List views
    path(
        'journals/',
        VoucherListView.as_view(),
        name='journal_list'
    ),

    # Create view
    path(
        'journals/create/',
        VoucherCreateView.as_view(),
        name='journal_create'
    ),
    path(
        'journals/create/<str:journal_type>/',
        VoucherCreateView.as_view(),
        name='journal_create_typed'
    ),

    # Detail view
    path(
        'journals/<int:pk>/',
        VoucherDetailView.as_view(),
        name='journal_detail'
    ),

    # Edit view
    path(
        'journals/<int:pk>/edit/',
        VoucherEditView.as_view(),
        name='journal_edit'
    ),

    # Post journal
    path(
        'journals/<int:pk>/post/',
        VoucherEditView.as_view(),
        {'action': 'post'},
        name='journal_post'
    ),

    # HTMX endpoints
    path(
        'journals/htmx/<str:action>/',
        VoucherHtmxHandler.as_view(),
        name='journal_htmx'
    ),
]

# Pattern: /accounting/journal/...
# These URLs should be included in the main accounting URLs as:
# path('journal/', include('accounting.urls_voucher')),
