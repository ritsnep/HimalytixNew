from __future__ import annotations

from types import SimpleNamespace

import pytest

from accounting.ird_service import (
    DEFAULT_IRD_TEST_ENDPOINT,
    build_ird_invoice_payload,
    sign_payload,
    submit_invoice_to_ird,
)


class FakeResponse:
    def __init__(self, body: dict):
        self._body = body
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.last_request = None

    def post(self, url, json=None, headers=None, timeout=None):
        self.last_request = {"url": url, "json": json, "headers": headers, "timeout": timeout}
        return FakeResponse({"ack_id": "ACK-123", "status": "ok"})


def test_sign_payload_is_deterministic():
    payload = {"b": 2, "a": 1}
    first = sign_payload(payload, "secret")
    second = sign_payload({"a": 1, "b": 2}, "secret")  # different ordering
    assert first == second
    # Hard-coded digest to guard against accidental changes
    assert first == "TZgTI1WHacRbuOq4cPaD+wIg0f3BUKOjG06jTEr237k="


def test_build_payload_with_basic_fields():
    organization = SimpleNamespace(name="Acme Corp", tax_id="PAN123")
    customer = SimpleNamespace(name="Buyer", tax_id="PAN789", billing_address="Kathmandu", phone="98000")
    line = SimpleNamespace(
        description="Product A",
        hsn_code="0101",
        quantity=2,
        unit_price=50,
        discount_amount=5,
        line_total=95,
        tax_amount=13,
        tax_code=SimpleNamespace(code="VAT13", rate=13),
    )
    invoice = SimpleNamespace(
        invoice_number="SI-001",
        invoice_date=None,
        subtotal=95,
        tax_total=13,
        total=108,
        currency="NPR",
        organization=organization,
        customer=customer,
        lines=[line],
    )

    payload = build_ird_invoice_payload(invoice)

    assert payload["invoiceNumber"] == "SI-001"
    assert payload["seller"]["pan"] == "PAN123"
    assert payload["buyer"]["pan"] == "PAN789"
    assert payload["lines"][0]["taxCode"] == "VAT13"
    assert payload["lines"][0]["lineTotal"] == 95.0


@pytest.mark.django_db
def test_submit_invoice_updates_metadata_and_uses_headers(settings):
    # Ensure settings fallback works
    settings.IRD_ENDPOINT = DEFAULT_IRD_TEST_ENDPOINT
    settings.IRD_SIGNING_SECRET = "secret"
    settings.IRD_API_KEY = "api-key"

    organization = SimpleNamespace(name="Acme", tax_id="PAN123")
    customer = SimpleNamespace(name="Buyer", tax_id="PAN456")
    invoice = SimpleNamespace(
        invoice_number="SI-99",
        invoice_date=None,
        subtotal=100,
        tax_total=13,
        total=113,
        currency="NPR",
        organization=organization,
        customer=customer,
        lines=[],
        metadata={},
        save=lambda update_fields=None: None,
    )

    session = FakeSession()
    result = submit_invoice_to_ird(
        invoice,
        session=session,
        endpoint="https://example.test/api",
        signing_secret="secret",
        api_key="token",
        timeout=5,
    )

    # Metadata persisted on the invoice object
    assert invoice.metadata.get("ird_ack_id") == "ACK-123"
    assert invoice.metadata.get("ird_signature") == sign_payload(result.payload, "secret")

    # Request header wiring
    assert session.last_request["url"] == "https://example.test/api"
    assert session.last_request["headers"]["Authorization"] == "Bearer token"
    assert "X-Signature" in session.last_request["headers"]

    # Result mirrors response
    assert result.ack_id == "ACK-123"
    assert result.response["status"] == "ok"
