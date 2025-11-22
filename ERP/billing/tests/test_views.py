from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from billing.models import CreditDebitNote, InvoiceHeader
from usermanagement.models import CustomUser, Organization


class BillingViewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org", code="ORG1", type="company")
        self.user = CustomUser.objects.create_user(username="tester", password="pass123")
        perms = Permission.objects.filter(codename__in=["add_invoiceheader", "change_invoiceheader", "view_invoiceauditlog"])
        self.user.user_permissions.add(*perms)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_invoice_via_api(self):
        url = reverse("billing:billing-invoice-list")
        payload = {
            "tenant": self.org.id,
            "invoice_date": timezone.now().date(),
            "customer_name": "Acme",
            "customer_pan": "123456789",
            "billing_address": "Kathmandu",
            "lines": [
                {"description": "Item", "quantity": "1", "unit_price": "50", "vat_rate": "13"},
            ],
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        invoice = InvoiceHeader.objects.first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.total_amount, Decimal("56.50"))

    def test_cancel_invoice_creates_note(self):
        invoice = InvoiceHeader.objects.create(
            tenant=self.org,
            invoice_date=timezone.now().date(),
            customer_name="Acme",
            customer_pan="123456789",
        )
        url = reverse("billing:billing-invoice-cancel", args=[invoice.id])
        response = self.client.post(url, {"reason": "Customer request"}, format="json")
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertTrue(invoice.canceled)
        self.assertEqual(CreditDebitNote.objects.filter(invoice=invoice).count(), 1)
