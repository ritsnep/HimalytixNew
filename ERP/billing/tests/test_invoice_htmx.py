from django.test import TestCase
from django.urls import reverse

from accounting.tests.factories import create_user


class SalesInvoiceHTMXTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client.force_login(self.user)

    def test_invoice_save_returns_partial_errors_for_htmx(self):
        url = reverse("billing:invoice_save")
        response = self.client.post(
            url,
            {},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("Select a customer", response.content.decode("utf-8"))
        self.assertEqual(response.headers.get("HX-Retarget"), "#sales-invoice-errors")
