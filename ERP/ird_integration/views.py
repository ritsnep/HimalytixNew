import json
from typing import Any, Dict, Optional, Tuple

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import IRDSettingsForm
from .models import IRDLog, IRDSettings, CreditNote, Invoice

IRD_BILL_ENDPOINT = "https://cbapi.ird.gov.np/api/bill"
IRD_BILLRETURN_ENDPOINT = "https://cbapi.ird.gov.np/api/billreturn"
REQUEST_TIMEOUT_SECONDS = 10


def _decimal_to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _serialize_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.strftime("%Y-%m-%d")
    except AttributeError:
        return str(value)


def _current_client_timestamp() -> str:
    return timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_invoice_payload(settings: IRDSettings, invoice: Invoice) -> Dict[str, Any]:
    return {
        "username": settings.username,
        "password": settings.password,
        "seller_pan": settings.seller_pan,
        "buyer_pan": invoice.buyer_pan,
        "buyer_name": invoice.buyer_name,
        "fiscal_year": invoice.fiscal_year,
        "invoice_number": invoice.invoice_number,
        "invoice_date": _serialize_date(invoice.invoice_date),
        "isrealtime": True,
        "datetimeClient": _current_client_timestamp(),
        "total_sales": _decimal_to_float(invoice.total_sales),
        "taxable_sales_vat": _decimal_to_float(invoice.taxable_sales_vat),
        "vat": _decimal_to_float(invoice.vat),
        "excisable_amount": _decimal_to_float(invoice.excisable_amount),
        "excise": _decimal_to_float(invoice.excise),
        "taxable_sales_hst": _decimal_to_float(invoice.taxable_sales_hst),
        "hst": _decimal_to_float(invoice.hst),
        "amount_for_esf": _decimal_to_float(invoice.amount_for_esf),
        "esf": _decimal_to_float(invoice.esf),
        "export_sales": _decimal_to_float(invoice.export_sales),
        "tax_exempted_sales": _decimal_to_float(invoice.tax_exempted_sales),
    }


def _build_creditnote_payload(settings: IRDSettings, credit_note: CreditNote) -> Dict[str, Any]:
    return {
        "username": settings.username,
        "password": settings.password,
        "seller_pan": settings.seller_pan,
        "buyer_pan": credit_note.buyer_pan,
        "buyer_name": credit_note.buyer_name,
        "fiscal_year": credit_note.fiscal_year,
        "credit_note_number": credit_note.credit_note_number,
        "credit_note_date": _serialize_date(credit_note.credit_note_date),
        "ref_invoice_number": credit_note.ref_invoice.invoice_number,
        "ref_invoice_date": _serialize_date(credit_note.ref_invoice.invoice_date),
        "reason_for_return": credit_note.reason_for_return,
        "isrealtime": True,
        "datetimeClient": _current_client_timestamp(),
        "total_sales": _decimal_to_float(credit_note.total_sales),
        "taxable_sales_vat": _decimal_to_float(credit_note.taxable_sales_vat),
        "vat": _decimal_to_float(credit_note.vat),
        "excisable_amount": _decimal_to_float(credit_note.excisable_amount),
        "excise": _decimal_to_float(credit_note.excise),
        "taxable_sales_hst": _decimal_to_float(credit_note.taxable_sales_hst),
        "hst": _decimal_to_float(credit_note.hst),
        "amount_for_esf": _decimal_to_float(credit_note.amount_for_esf),
        "esf": _decimal_to_float(credit_note.esf),
        "export_sales": _decimal_to_float(credit_note.export_sales),
        "tax_exempted_sales": _decimal_to_float(credit_note.tax_exempted_sales),
    }


def _parse_response(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _extract_error_code(body: Any) -> Optional[int]:
    if isinstance(body, dict):
        for key in ("error_code", "code", "responseCode", "statusCode"):
            value = body.get(key)
            if isinstance(value, int):
                return value
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    if isinstance(body, str):
        try:
            return int(body.strip())
        except ValueError:
            return None
    return None


def _response_signals_success(body: Any, http_status: int) -> bool:
    if http_status == 200:
        if isinstance(body, dict):
            status_value = body.get("status") or body.get("responseStatus")
            if isinstance(status_value, str) and status_value.lower() in {"ok", "success"}:
                return True
        code = _extract_error_code(body)
        if code in {None, 200}:
            return True
    return False


def _submit_to_ird(endpoint: str, payload: Dict[str, Any]) -> Tuple[bool, Any, str, Optional[int]]:
    try:
        response = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = _parse_response(response)
        success = _response_signals_success(body, response.status_code)
        return success, body, response.text, _extract_error_code(body)
    except requests.RequestException as exc:
        body = getattr(exc.response, "text", str(exc))
        return False, body, str(exc), getattr(exc.response, "status_code", None)


def _log_submission(
    *,
    invoice: Optional[Invoice] = None,
    credit_note: Optional[CreditNote] = None,
    payload: Dict[str, Any],
    response_body: Any,
    response_text: str,
    success: bool,
) -> None:
    IRDLog.objects.create(
        invoice=invoice,
        credit_note=credit_note,
        request_payload=json.dumps(payload),
        response_payload=json.dumps(response_body) if isinstance(response_body, (dict, list)) else str(response_text),
        success=success,
    )


@login_required
def ird_settings_view(request):
    settings_obj = IRDSettings.objects.first()
    if request.method == "POST":
        form = IRDSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "IRD settings updated successfully.")
            return redirect("ird_integration:ird_settings")
    else:
        form = IRDSettingsForm(instance=settings_obj)
    return render(request, "ird_integration/settings.html", {"form": form})


@login_required
def invoice_list_view(request):
    invoices = Invoice.objects.all()
    return render(request, "ird_integration/invoice_list.html", {"invoices": invoices})


@login_required
def creditnote_list_view(request):
    credit_notes = CreditNote.objects.select_related("ref_invoice").all()
    return render(request, "ird_integration/creditnote_list.html", {"credit_notes": credit_notes})


@require_http_methods(["POST"])
@login_required
def resend_invoice_view(request, pk: int):
    invoice = get_object_or_404(Invoice, pk=pk)
    settings_obj = IRDSettings.objects.first()
    if not settings_obj:
        raise Http404("IRD settings are not configured yet.")

    payload = _build_invoice_payload(settings_obj, invoice)
    success, body, payload_text, _ = _submit_to_ird(IRD_BILL_ENDPOINT, payload)

    _log_submission(
        invoice=invoice,
        payload=payload,
        response_body=body,
        response_text=payload_text,
        success=success,
    )

    invoice.status = Invoice.STATUS_SUCCESS if success else Invoice.STATUS_FAILED
    invoice.error_message = "" if success else str(body)
    invoice.save(update_fields=["status", "error_message", "updated_at"])
    return render(request, "ird_integration/invoice_row.html", {"invoice": invoice})


@require_http_methods(["POST"])
@login_required
def resend_creditnote_view(request, pk: int):
    credit_note = get_object_or_404(CreditNote, pk=pk)
    settings_obj = IRDSettings.objects.first()
    if not settings_obj:
        raise Http404("IRD settings are not configured yet.")

    payload = _build_creditnote_payload(settings_obj, credit_note)
    success, body, payload_text, _ = _submit_to_ird(IRD_BILLRETURN_ENDPOINT, payload)

    _log_submission(
        credit_note=credit_note,
        payload=payload,
        response_body=body,
        response_text=payload_text,
        success=success,
    )

    credit_note.status = Invoice.STATUS_SUCCESS if success else Invoice.STATUS_FAILED
    credit_note.error_message = "" if success else str(body)
    credit_note.save(update_fields=["status", "error_message", "updated_at"])
    return render(request, "ird_integration/creditnote_row.html", {"credit_note": credit_note})
