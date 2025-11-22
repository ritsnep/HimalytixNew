from __future__ import annotations

import time
from typing import Optional

import requests
from django.conf import settings

from .models import InvoiceHeader, InvoiceAuditLog


class CBMSClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, session: Optional[requests.Session] = None):
        self.base_url = base_url or getattr(settings, "CBMS_API_URL", "")
        self.api_key = api_key or getattr(settings, "CBMS_API_KEY", "")
        self.session = session or requests.Session()

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def sync_invoice(self, invoice: InvoiceHeader) -> dict:
        payload = self._serialize_invoice(invoice)
        resp = self.session.post(self.base_url, json=payload, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _serialize_invoice(self, invoice: InvoiceHeader) -> dict:
        return {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat(),
            "customer_name": invoice.customer_name,
            "customer_pan": invoice.customer_pan,
            "taxable_amount": str(invoice.taxable_amount),
            "vat_amount": str(invoice.vat_amount),
            "total_amount": str(invoice.total_amount),
            "lines": [
                {
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                    "vat_rate": str(line.vat_rate),
                    "vat_amount": str(line.vat_amount),
                    "line_total": str(line.line_total),
                }
                for line in invoice.lines.all()
            ],
        }


def sync_with_cbms(invoice: InvoiceHeader, client: Optional[CBMSClient] = None, retries: int = 3, backoff: float = 1.0) -> None:
    client = client or CBMSClient()
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = client.sync_invoice(invoice)
            invoice._allow_update = True
            invoice.sync_status = "synced"
            invoice.save(update_fields=["sync_status", "updated_at"])
            InvoiceAuditLog.objects.create(invoice=invoice, action="sync", description=str(response))
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(backoff * attempt)
    invoice._allow_update = True
    invoice.sync_status = "failed"
    invoice.save(update_fields=["sync_status", "updated_at"])
    InvoiceAuditLog.objects.create(invoice=invoice, action="sync", description=f"Failed: {last_exc}")


def resync_failed_invoices(limit: Optional[int] = None) -> int:
    qs = InvoiceHeader.objects.filter(sync_status="failed", canceled=False).order_by("id")
    if limit:
        qs = qs[:limit]
    count = 0
    client = CBMSClient()
    for invoice in qs:
        sync_with_cbms(invoice, client=client)
        count += 1
    return count
