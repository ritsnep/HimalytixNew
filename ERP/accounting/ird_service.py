"""Lightweight Nepal IRD eBilling helper utilities.

This module keeps the integration surface small and testable while we firm up
the exact IRD contract. It provides:
    * Payload builder from an invoice-like object
    * Deterministic signing helper (HMAC-SHA256 for the default test flow)
    * Submission helper that can target the public IRD test gateway (“ofird”)
      or a custom endpoint passed at call time.

The helpers intentionally avoid hard dependencies on specific model classes so
they can be reused in unit tests with simple stubs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date
import time
from typing import Any, Dict, Iterable, Optional

import requests
from django.conf import settings

# Known IRD gateways. `ofird` is the public test sandbox; `cbms` is production.
DEFAULT_IRD_TEST_ENDPOINT = "https://ofird.ird.gov.np/api/bill"
DEFAULT_IRD_PROD_ENDPOINT = "https://cbms.ird.gov.np/api/bill"


def _serialize_date(value: Any) -> Optional[str]:
    """Convert date/datetime-like values to ISO strings when possible."""
    if isinstance(value, (date,)):
        return value.isoformat()
    try:
        # Django DateField values are already date objects; strings pass through.
        return value.isoformat()  # type: ignore[attr-defined]
    except Exception:
        return None


def _safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def _iter_lines(invoice: Any) -> Iterable[Any]:
    """Yield invoice lines from either a Django related manager or a plain list."""
    lines = _safe_getattr(invoice, "lines", []) or []
    if hasattr(lines, "all"):
        return lines.all()
    return lines


def build_ird_invoice_payload(invoice: Any) -> Dict[str, Any]:
    """
    Build a minimal IRD-style payload from an invoice-like object.

    The structure follows common CBMS fields; it can be expanded when the
    finalized schema is available. Field names are camelCase to align with
    typical IRD examples.
    """
    organization = _safe_getattr(invoice, "organization")
    customer = _safe_getattr(invoice, "customer")

    payload: Dict[str, Any] = {
        "invoiceNumber": _safe_getattr(invoice, "invoice_number"),
        "invoiceDate": _serialize_date(_safe_getattr(invoice, "invoice_date")),
        "buyer": {
            "name": _safe_getattr(customer, "name") or _safe_getattr(customer, "customer_display_name"),
            "pan": _safe_getattr(customer, "tax_id"),
            "address": _safe_getattr(customer, "billing_address"),
            "contact": _safe_getattr(customer, "phone"),
            "email": _safe_getattr(customer, "email"),
        },
        "seller": {
            "name": _safe_getattr(organization, "legal_name") or _safe_getattr(organization, "name"),
            "pan": _safe_getattr(organization, "tax_id"),
            "address": _safe_getattr(organization, "address"),
            "contact": _safe_getattr(organization, "phone"),
            "email": _safe_getattr(organization, "email"),
        },
        "currency": str(_safe_getattr(invoice, "currency") or ""),
        "subtotal": _safe_getattr(invoice, "subtotal", 0),
        "taxTotal": _safe_getattr(invoice, "tax_total", 0),
        "grandTotal": _safe_getattr(invoice, "total", 0),
        "lines": [],
    }

    for line in _iter_lines(invoice):
        payload["lines"].append(
            {
                "description": _safe_getattr(line, "description"),
                "hsn": _safe_getattr(line, "hsn_code"),
                "quantity": float(_safe_getattr(line, "quantity", 0)),
                "unitPrice": float(_safe_getattr(line, "unit_price", 0)),
                "discount": float(_safe_getattr(line, "discount_amount", 0)),
                "lineTotal": float(_safe_getattr(line, "line_total", 0)),
                "taxCode": _safe_getattr(_safe_getattr(line, "tax_code"), "code"),
                "taxRate": float(_safe_getattr(_safe_getattr(line, "tax_code"), "rate", 0)),
                "taxAmount": float(_safe_getattr(line, "tax_amount", 0)),
            }
        )

    return payload


def sign_payload(payload: Dict[str, Any], secret: str) -> str:
    """
    Generate a deterministic HMAC-SHA256 signature over the canonical JSON.

    IRD production often uses RSA signatures; this HMAC signer is a safe default
    for the `ofird` test gateway and keeps tests dependency-light. Swap the
    implementation once the official signing algorithm is confirmed.
    """
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


@dataclass
class IRDSubmissionResult:
    payload: Dict[str, Any]
    signature: str
    ack_id: Optional[str]
    response: Dict[str, Any]


def _update_invoice_metadata(invoice: Any, updates: Dict[str, Any]) -> None:
    """Merge IRD-related metadata back to the invoice if it exposes a metadata field."""
    if not hasattr(invoice, "metadata"):
        return
    current = getattr(invoice, "metadata", {}) or {}
    current.update(updates)
    invoice.metadata = current
    if hasattr(invoice, "save"):
        try:
            invoice.save(update_fields=["metadata", "updated_at"])
        except Exception:
            # Best-effort persistence; do not break the submission on metadata save failures.
            pass


def submit_invoice_to_ird(
    invoice: Any,
    *,
    session: Optional[requests.Session] = None,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    signing_secret: Optional[str] = None,
    timeout: int = 10,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
) -> IRDSubmissionResult:
    """
    Submit a single invoice to the IRD gateway.

    Args:
        invoice: An object exposing invoice_number, invoice_date, totals and line items.
        session: Optional requests.Session for easier testing/mocking.
        endpoint: Override the IRD URL; defaults to settings.IRD_ENDPOINT or the public test gateway.
        api_key: IRD-issued API key/token if required by the gateway.
        signing_secret: Shared secret for HMAC signing; falls back to settings.IRD_SIGNING_SECRET.
        timeout: HTTP timeout in seconds.
    """
    session = session or requests.Session()
    endpoint = endpoint or getattr(settings, "IRD_ENDPOINT", DEFAULT_IRD_TEST_ENDPOINT)
    signing_secret = signing_secret or getattr(settings, "IRD_SIGNING_SECRET", "")

    payload = build_ird_invoice_payload(invoice)
    signature = sign_payload(payload, signing_secret)

    headers = {"Content-Type": "application/json", "X-Signature": signature}
    if api_key := api_key or getattr(settings, "IRD_API_KEY", None):
        headers["Authorization"] = f"Bearer {api_key}"

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.post(endpoint, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(backoff_seconds * attempt)

    try:
        body = response.json()
    except ValueError:
        body = {}

    ack_id = (
        body.get("ack_id")
        or body.get("referenceNo")
        or body.get("reference")
        or body.get("billNo")
    )

    updates = {
        "ird_signature": signature,
        "ird_ack_id": ack_id,
        "ird_last_payload": payload,
        "ird_last_response": body,
        "ird_last_submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ird_status": body.get("status") or body.get("responseStatus"),
    }
    for attr, value in updates.items():
        if hasattr(invoice, attr):
            setattr(invoice, attr, value)
    if hasattr(invoice, "save"):
        try:
            invoice.save(update_fields=[k for k in updates.keys() if hasattr(invoice, k)] + ["updated_at"])
        except Exception:
            # Best-effort persistence; do not break the submission on metadata save failures.
            pass

    _update_invoice_metadata(invoice, updates)

    return IRDSubmissionResult(
        payload=payload,
        signature=signature,
        ack_id=ack_id,
        response=body,
    )
