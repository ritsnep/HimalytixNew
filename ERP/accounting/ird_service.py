"""Lightweight Nepal IRD eBilling helper utilities.

The helper surface remains small so it is easy to evolve as the official IRD
contract changes. It includes:
- Payload builder from an invoice-like object
- Pluggable signing (HMAC-SHA256 for the public test gateway, RSA-SHA256 for
  production CBMS)
- Submission helper for both ofird (test) and cbms (production) endpoints

Hard dependencies on concrete Django models are avoided; simple stubs work
fine in tests.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, Optional

import requests
from django.conf import settings
from django.utils import timezone

# Known IRD gateways. `ofird` is the public test sandbox; `cbms` is production.
DEFAULT_IRD_TEST_ENDPOINT = "https://ofird.ird.gov.np/api/bill"
DEFAULT_IRD_PROD_ENDPOINT = "https://cbms.ird.gov.np/api/bill"

DEFAULT_SIGNING_METHOD = "hmac"  # "hmac" (test) or "rsa" (production)


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


def _decimal_to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _derive_fiscal_year_code(invoice: Any) -> Optional[str]:
    """Attempt to derive a fiscal year code without tightly coupling to models."""
    explicit_code = _safe_getattr(invoice, "ird_fiscal_year_code") or _safe_getattr(invoice, "fiscal_year_code")
    if explicit_code:
        return str(explicit_code)

    fiscal_year = _safe_getattr(invoice, "fiscal_year") or _safe_getattr(_safe_getattr(invoice, "period"), "fiscal_year")
    if fiscal_year:
        code = _safe_getattr(fiscal_year, "code") or _safe_getattr(fiscal_year, "name")
        if code:
            return str(code)

    document_date = _safe_getattr(invoice, "invoice_date") or _safe_getattr(invoice, "journal_date")
    organization = _safe_getattr(invoice, "organization")
    if organization and document_date:
        try:
            from accounting.models import FiscalYear  # Local import to avoid circularity

            fy = FiscalYear.get_for_date(organization, document_date)
            if fy:
                return fy.code
        except Exception:
            pass
        year = getattr(document_date, "year", None)
        return str(year) if year else None
    return None


def build_ird_invoice_payload(invoice: Any) -> Dict[str, Any]:
    """
    Build an IRD CBMS-style payload from an invoice-like object.

    The structure follows public CBMS examples (snake_case, fiscal-year
    numbering, VAT totals) and keeps buyer/seller blocks for readability.
    """
    organization = _safe_getattr(invoice, "organization")
    customer = _safe_getattr(invoice, "customer")

    fiscal_year_code = _derive_fiscal_year_code(invoice)

    subtotal = _safe_getattr(invoice, "subtotal", 0)
    tax_total = _safe_getattr(invoice, "tax_total", 0)
    grand_total = _safe_getattr(invoice, "total", 0)
    service_charge = _safe_getattr(invoice, "service_charge", 0)
    excise = _safe_getattr(invoice, "excise_duty", 0)
    digital_payment_amount = _safe_getattr(invoice, "ird_digital_payment_amount", None)
    digital_payment_txn_id = _safe_getattr(invoice, "ird_digital_payment_txn_id", None)

    payload: Dict[str, Any] = {
        # CBMS-required fields
        "seller_pan": _safe_getattr(organization, "tax_id"),
        "seller_name": _safe_getattr(organization, "legal_name") or _safe_getattr(organization, "name"),
        "buyer_pan": _safe_getattr(customer, "tax_id"),
        "buyer_name": _safe_getattr(customer, "name") or _safe_getattr(customer, "customer_display_name"),
        "buyer_address": _safe_getattr(customer, "billing_address") or _safe_getattr(customer, "address"),
        "buyer_contact": _safe_getattr(customer, "phone"),
        "fiscal_year": fiscal_year_code,
        "invoice_number": _safe_getattr(invoice, "invoice_number"),
        "invoice_date": _serialize_date(_safe_getattr(invoice, "invoice_date")),
        "isrealtime": bool(_safe_getattr(invoice, "ird_is_realtime", True)),
        "total_sales": _decimal_to_float(grand_total or (subtotal or 0) + (tax_total or 0)),
        "taxable_sales_vat": _decimal_to_float(subtotal),
        "vat": _decimal_to_float(tax_total),
        "service_charge": _decimal_to_float(service_charge),
        "excise": _decimal_to_float(excise),
        "currency": str(_safe_getattr(invoice, "currency") or ""),
        # Optional IRD extensions
        "digital_payment_amount": _decimal_to_float(digital_payment_amount) if digital_payment_amount else None,
        "digital_payment_txn_id": digital_payment_txn_id,
        # Structured details retained for traceability
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
        "lines": [],
    }

    for line in _iter_lines(invoice):
        taxable_amount = _decimal_to_float(_safe_getattr(line, "line_total", 0))
        vat_amount = _decimal_to_float(_safe_getattr(line, "tax_amount", 0))
        discount_amount = _decimal_to_float(_safe_getattr(line, "discount_amount", 0))

        payload["lines"].append(
            {
                "item_desc": _safe_getattr(line, "description"),
                "hsn": _safe_getattr(line, "hsn_code"),
                "qty": _decimal_to_float(_safe_getattr(line, "quantity", 0)),
                "unit_price": _decimal_to_float(_safe_getattr(line, "unit_price", 0)),
                "discount_amount": discount_amount,
                "taxable_amount": taxable_amount,
                "vat": vat_amount,
                "tax_code": _safe_getattr(_safe_getattr(line, "tax_code"), "code"),
                "tax_rate": _decimal_to_float(_safe_getattr(_safe_getattr(line, "tax_code"), "rate", 0)),
            }
        )

    return payload


def _sign_with_hmac(payload: Dict[str, Any], secret: str) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _sign_with_rsa(payload: Dict[str, Any], private_key_pem: str, passphrase: Optional[str] = None) -> str:
    """
    RSA-SHA256 signer for production CBMS environments.

    The cryptography package is only required if RSA signing is enabled.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("RSA signing requested but cryptography is not installed.") from exc

    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=passphrase.encode("utf-8") if passphrase else None,
    )
    signature = key.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def sign_payload(
    payload: Dict[str, Any],
    hmac_secret: Optional[str] = None,
    *,
    method: str = DEFAULT_SIGNING_METHOD,
    rsa_private_key: Optional[str] = None,
    rsa_passphrase: Optional[str] = None,
) -> str:
    """
    Sign a payload using either HMAC-SHA256 (default) or RSA-SHA256.

    Args:
        payload: JSON-serializable payload to sign.
        method: "hmac" or "rsa".
        hmac_secret: Shared secret for HMAC signing (required when method="hmac").
        rsa_private_key: PEM-encoded private key (required when method="rsa").
        rsa_passphrase: Optional passphrase for encrypted RSA keys.
    """
    method = (method or DEFAULT_SIGNING_METHOD).lower()
    if method not in {"hmac", "rsa"}:
        raise ValueError(f"Unsupported signing method: {method}")

    if method == "rsa":
        if not rsa_private_key:
            raise ValueError("RSA signing requires a PEM-encoded private key.")
        return _sign_with_rsa(payload, rsa_private_key, rsa_passphrase)

    if not hmac_secret:
        raise ValueError("HMAC signing requires a shared secret.")
    return _sign_with_hmac(payload, hmac_secret)


@dataclass
class IRDSubmissionResult:
    payload: Dict[str, Any]
    signature: str
    ack_id: Optional[str]
    response: Dict[str, Any]


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


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
    signing_method: Optional[str] = None,
    rsa_private_key: Optional[str] = None,
    rsa_passphrase: Optional[str] = None,
    auth_username: Optional[str] = None,
    auth_password: Optional[str] = None,
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
        signing_method: "hmac" (default) or "rsa"; defaults to settings.IRD_SIGNING_METHOD or hmac.
        rsa_private_key: PEM private key used when signing_method="rsa"; defaults to settings.IRD_RSA_PRIVATE_KEY.
        rsa_passphrase: Optional passphrase for encrypted RSA keys.
        auth_username/auth_password: IRD basic auth credentials (if required).
        timeout: HTTP timeout in seconds.
    """
    session = session or requests.Session()
    endpoint = endpoint or getattr(settings, "IRD_ENDPOINT", DEFAULT_IRD_TEST_ENDPOINT)
    signing_method = signing_method or getattr(settings, "IRD_SIGNING_METHOD", DEFAULT_SIGNING_METHOD)
    signing_secret = signing_secret or getattr(settings, "IRD_SIGNING_SECRET", "")
    rsa_private_key = rsa_private_key or getattr(settings, "IRD_RSA_PRIVATE_KEY", None)
    rsa_passphrase = rsa_passphrase or getattr(settings, "IRD_RSA_PRIVATE_KEY_PASSPHRASE", None)

    payload = build_ird_invoice_payload(invoice)
    signature = sign_payload(
        payload,
        method=signing_method,
        hmac_secret=signing_secret,
        rsa_private_key=rsa_private_key,
        rsa_passphrase=rsa_passphrase,
    )

    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "X-Signature-Method": signing_method,
    }
    if api_key := api_key or getattr(settings, "IRD_API_KEY", None):
        headers["Authorization"] = f"Bearer {api_key}"
    if auth_username := auth_username or getattr(settings, "IRD_USERNAME", None):
        auth_password = auth_password or getattr(settings, "IRD_PASSWORD", "")
        headers["Authorization"] = _basic_auth_header(auth_username, auth_password)

    last_exc: Optional[Exception] = None
    response = None
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
        body = response.json() if response else {}
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


def record_invoice_print(
    invoice: Any,
    *,
    reason: Optional[str] = None,
    is_reprint: bool = True,
) -> None:
    """
    Track invoice print and reprint events for IRD audit needs.

    This helper increments counters and timestamps; caller is responsible for
    enforcing permissions on reprints.
    """
    fields_to_update = []

    if hasattr(invoice, "ird_last_printed_at"):
        invoice.ird_last_printed_at = timezone.now()
        fields_to_update.append("ird_last_printed_at")

    if is_reprint and hasattr(invoice, "ird_reprint_count"):
        current = getattr(invoice, "ird_reprint_count") or 0
        invoice.ird_reprint_count = current + 1
        fields_to_update.append("ird_reprint_count")

    if reason and hasattr(invoice, "ird_last_reprint_reason") and is_reprint:
        invoice.ird_last_reprint_reason = reason
        fields_to_update.append("ird_last_reprint_reason")

    if hasattr(invoice, "save") and fields_to_update:
        try:
            invoice.save(update_fields=fields_to_update + ["updated_at"])
        except Exception:
            # Best-effort logging; do not block UI.
            pass
