# billing/urls.py
"""
URL Configuration for Billing Module
"""
from django.urls import path
from billing import views

urlpatterns = [
    # Main invoice views
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoice/create/', views.invoice_create, name='invoice_create'),
    path('invoice/<uuid:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/<uuid:invoice_id>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoice/<uuid:invoice_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('invoice/save/', views.invoice_save, name='invoice_save'),
    
    # HTMX endpoints for dynamic interactions
    path('htmx/customer-search/', views.customer_search, name='customer_search'),
    path('htmx/product-search/', views.product_search, name='product_search'),
    path('htmx/add-line/', views.add_invoice_line, name='add_invoice_line'),
    path('htmx/calculate-line/', views.calculate_line_total, name='calculate_line_total'),
    path('htmx/calculate-total/', views.calculate_invoice_total, name='calculate_invoice_total'),
    
    # IRD operations
    path('invoice/<uuid:invoice_id>/submit-ird/', views.submit_to_ird, name='submit_to_ird'),
    path('invoice/<uuid:invoice_id>/cancel/', views.cancel_invoice, name='cancel_invoice'),
    
    # Export/Import
    path('export/tally/', views.export_tally, name='export_tally'),
]

