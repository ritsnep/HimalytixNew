# accounting/urls/invoice_urls.py
"""
URL patterns for IRD-integrated sales invoice views
"""
from django.urls import path
from accounting.views.ird_invoice_views import (
    SalesInvoiceListView,
    SalesInvoiceDetailView,
    SalesInvoiceCreateView,
    SalesInvoiceUpdateView,
    IRDStatusDashboardView,
    submit_invoice_to_ird,
    cancel_invoice_in_ird,
    print_invoice,
    get_invoice_qr_code,
    batch_submit_to_ird,
    post_invoice,
    get_customer_details,
)

app_name = 'accounting'

urlpatterns = [
    # Invoice CRUD
    path('invoices/', SalesInvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', SalesInvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:invoice_id>/', SalesInvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:invoice_id>/edit/', SalesInvoiceUpdateView.as_view(), name='invoice_edit'),
    
    # Invoice Actions
    path('invoices/<int:invoice_id>/post/', post_invoice, name='invoice_post'),
    path('invoices/<int:invoice_id>/print/', print_invoice, name='invoice_print'),
    
    # IRD Integration
    path('invoices/<int:invoice_id>/submit-ird/', submit_invoice_to_ird, name='invoice_submit_ird'),
    path('invoices/<int:invoice_id>/cancel-ird/', cancel_invoice_in_ird, name='invoice_cancel_ird'),
    path('invoices/<int:invoice_id>/qr-code/', get_invoice_qr_code, name='invoice_qr_code'),
    path('invoices/batch-submit-ird/', batch_submit_to_ird, name='invoice_batch_submit_ird'),
    
    # IRD Dashboard
    path('ird-dashboard/', IRDStatusDashboardView.as_view(), name='ird_dashboard'),
    
    # AJAX Endpoints
    path('ajax/customer/<int:customer_id>/', get_customer_details, name='ajax_customer_details'),
]
