from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounting.models import Customer, SalesOrder
from accounting.services.sales_order_service import SalesOrderService
from accounting.tests.factories import (
    create_account_type,
    create_chart_of_account,
    create_currency,
    create_fiscal_year,
    create_organization,
    create_user,
)


class SalesOrderServiceTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.currency = create_currency(code=self.organization.base_currency_code or "USD")
        create_fiscal_year(organization=self.organization)
        self.order_date = timezone.now().date()
        self.account_type = create_account_type(nature="asset")
        self.ar_account = create_chart_of_account(
            organization=self.organization,
            account_type=self.account_type,
        )
        self.rev_account = create_chart_of_account(
            organization=self.organization,
            account_type=self.account_type,
        )
        self.user = create_user(organization=self.organization)
        self.customer = Customer.objects.create(
            organization=self.organization,
            code="CUST001",
            display_name="Acme Corp",
            accounts_receivable_account=self.ar_account,
            revenue_account=self.rev_account,
        )
        self.customer.default_currency = self.currency
        self.customer.save(update_fields=["default_currency"])
        self.service = SalesOrderService(self.user)

    def _lines(self):
        return [
            {
                "description": "Consulting",
                "product_code": "CONSULT",
                "quantity": Decimal("2"),
                "unit_price": Decimal("50"),
                "discount_amount": Decimal("10"),
                "revenue_account": self.rev_account,
                "tax_amount": Decimal("0"),
                "tax_code": None,
            },
            {
                "description": "Subscription",
                "product_code": "SUB",
                "quantity": Decimal("1"),
                "unit_price": Decimal("200"),
                "discount_amount": Decimal("0"),
                "revenue_account": self.rev_account,
                "tax_amount": Decimal("5"),
                "tax_code": None,
            },
        ]

    def test_create_order_generates_number_and_totals(self):
        order = self.service.create_order(
            organization=self.organization,
            customer=self.customer,
            currency=self.currency,
            order_date=self.order_date,
            expected_ship_date=self.order_date + timedelta(days=5),
            exchange_rate=Decimal("1"),
            lines=self._lines(),
        )
        self.assertIn("SO-", order.order_number)
        self.assertEqual(order.subtotal, Decimal("290"))
        self.assertEqual(order.tax_total, Decimal("5"))
        self.assertEqual(order.total, Decimal("295"))
        self.assertEqual(order.lines.count(), 2)

    def test_transition_status_respects_allowed_graph(self):
        order = self.service.create_order(
            organization=self.organization,
            customer=self.customer,
            currency=self.currency,
            order_date=self.order_date,
            lines=self._lines(),
        )
        with self.assertRaises(ValidationError):
            self.service.transition_status(order, "fulfilled")
        self.service.transition_status(order, "confirmed")
        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")

    def test_convert_to_invoice_links_document(self):
        order = self.service.create_order(
            organization=self.organization,
            customer=self.customer,
            currency=self.currency,
            order_date=self.order_date,
            lines=self._lines(),
        )
        invoice = self.service.convert_to_invoice(order, invoice_date=self.order_date + timedelta(days=1))
        self.assertIsNotNone(invoice.pk)
        order.refresh_from_db()
        self.assertEqual(order.status, "invoiced")
        self.assertEqual(order.linked_invoice_id, invoice.pk)


class SalesOrderViewTests(TestCase):
    def setUp(self):
        self.organization = create_organization()
        self.currency = create_currency(code=self.organization.base_currency_code or "USD")
        create_fiscal_year(organization=self.organization)
        self.order_date = timezone.now().date()
        account_type = create_account_type(nature="asset")
        self.ar_account = create_chart_of_account(
            organization=self.organization,
            account_type=account_type,
        )
        self.rev_account = create_chart_of_account(
            organization=self.organization,
            account_type=account_type,
        )
        self.customer = Customer.objects.create(
            organization=self.organization,
            code="CUST100",
            display_name="Waypoint LLC",
            accounts_receivable_account=self.ar_account,
            revenue_account=self.rev_account,
        )
        self.customer.default_currency = self.currency
        self.customer.save(update_fields=["default_currency"])
        self.user = create_user(organization=self.organization, username="sales-admin")
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_view_persists_sales_order(self):
        url = reverse("accounting:sales_order_create")
        data = {
            "customer": str(self.customer.pk),
            "order_date": self.order_date.isoformat(),
            "expected_ship_date": (self.order_date + timedelta(days=5)).isoformat(),
            "reference_number": "REF-123",
            "notes": "Expedite",
            "currency": self.currency.pk,
            "exchange_rate": "1",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-id": "",
            "lines-0-description": "Subscription",
            "lines-0-product_code": "SUB",
            "lines-0-quantity": "1",
            "lines-0-unit_price": "100",
            "lines-0-discount_amount": "0",
            "lines-0-revenue_account": str(self.rev_account.pk),
            "lines-0-tax_code": "",
            "lines-0-tax_amount": "0",
            "lines-0-DELETE": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.context['form'].errors)
        self.assertTrue(response.url.endswith(reverse("accounting:sales_order_list")))
        self.assertEqual(SalesOrder.objects.count(), 1)
        order = SalesOrder.objects.first()
        self.assertEqual(order.total, Decimal("100"))

    def test_list_view_renders_orders(self):
        service = SalesOrderService(self.user)
        service.create_order(
            organization=self.organization,
            customer=self.customer,
            currency=self.currency,
            order_date=self.order_date,
            lines=[
                {
                    "description": "Implementation",
                    "product_code": "IMP",
                    "quantity": Decimal("1"),
                    "unit_price": Decimal("250"),
                    "discount_amount": Decimal("0"),
                    "revenue_account": self.rev_account,
                    "tax_code": None,
                    "tax_amount": Decimal("0"),
                }
            ],
        )
        response = self.client.get(reverse("accounting:sales_order_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.display_name)
