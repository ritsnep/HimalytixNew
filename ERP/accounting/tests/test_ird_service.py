from datetime import date

from django.test import SimpleTestCase

from accounting import ird_service


class _Stub:
    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)


class IRDServiceTests(SimpleTestCase):
    def test_build_payload_matches_cbms_fields(self):
        org = _Stub(tax_id="123456789", legal_name="Himalytix Pvt Ltd", address="Kathmandu")
        customer = _Stub(
            tax_id="987654321",
            name="Everest Retail",
            billing_address="Lalitpur",
            phone="+977-1-5555555",
            email="ops@example.com",
        )
        line = _Stub(
            description="Service fee",
            hsn_code="9983",
            quantity=2,
            unit_price=50,
            discount_amount=0,
            line_total=100,
            tax_amount=13,
            tax_code=_Stub(code="VAT13", rate=13),
        )
        invoice = _Stub(
            organization=org,
            customer=customer,
            invoice_number="SI-25/26-0001",
            invoice_date=date(2025, 1, 5),
            subtotal=100,
            tax_total=13,
            total=113,
            currency="NPR",
            ird_is_realtime=True,
            ird_fiscal_year_code="FY25/26",
            ird_digital_payment_amount=15.5,
            ird_digital_payment_txn_id="TXN123",
            lines=[line],
        )

        payload = ird_service.build_ird_invoice_payload(invoice)

        self.assertEqual(payload["invoice_number"], "SI-25/26-0001")
        self.assertEqual(payload["fiscal_year"], "FY25/26")
        self.assertTrue(payload["isrealtime"])
        self.assertAlmostEqual(payload["taxable_sales_vat"], 100.0)
        self.assertAlmostEqual(payload["vat"], 13.0)
        self.assertAlmostEqual(payload["digital_payment_amount"], 15.5)
        self.assertEqual(payload["digital_payment_txn_id"], "TXN123")
        self.assertEqual(payload["lines"][0]["item_desc"], "Service fee")
        self.assertEqual(payload["lines"][0]["tax_code"], "VAT13")

    def test_sign_payload_hmac(self):
        payload = {"a": 1}
        signature = ird_service.sign_payload(payload, method="hmac", hmac_secret="secret")
        self.assertEqual(signature, "qp4uNXX11wmLbKzNeQiIw21f22M0KnO62i1qUXR6hJQ=")
