from django.urls import path

from . import views

app_name = "ird_integration"
urlpatterns = [
    path("settings/", views.ird_settings_view, name="ird_settings"),
    path("invoices/", views.invoice_list_view, name="invoice_list"),
    path("invoices/resend/<int:pk>/", views.resend_invoice_view, name="resend_invoice"),
    path("credit-notes/", views.creditnote_list_view, name="creditnote_list"),
    path(
        "credit-notes/resend/<int:pk>/",
        views.resend_creditnote_view,
        name="resend_creditnote",
    ),
]
