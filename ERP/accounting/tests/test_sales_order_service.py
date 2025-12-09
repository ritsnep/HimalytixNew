from decimal import Decimal

from django.test import SimpleTestCase
from django.core.exceptions import ValidationError

from accounting.services.sales_order_service import SalesOrderService


class SalesOrderServiceValidationTests(SimpleTestCase):
    def test_line_validation_requires_positive_quantity(self):
        service = SalesOrderService(user=None)
        with self.assertRaises(ValidationError):
            service._validate_line_payload([
                {
                    "description": "Widget",
                    "product_code": "W-1",
                    "quantity": Decimal("0"),
                    "unit_price": Decimal("10"),
                }
            ])

    def test_line_validation_calculates_line_total(self):
        service = SalesOrderService(user=None)
        payload = service._validate_line_payload([
            {
                "description": "Widget",
                "product_code": "W-1",
                "quantity": Decimal("2"),
                "unit_price": Decimal("10"),
                "discount_amount": Decimal("1"),
            }
        ])
        self.assertEqual(payload[0]["line_total"], Decimal("19"))
