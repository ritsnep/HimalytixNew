from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, CreditDebitNoteViewSet, InvoiceViewSet

app_name = "billing"

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="billing-invoice")
router.register(r"notes", CreditDebitNoteViewSet, basename="billing-note")
router.register(r"logs", AuditLogViewSet, basename="billing-log")

urlpatterns = [
    path("", include(router.urls)),
]
