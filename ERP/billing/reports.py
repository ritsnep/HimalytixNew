from __future__ import annotations

import csv
import io
from datetime import date
from typing import Iterable, Tuple

import pandas as pd  # type: ignore
from django.db.models import QuerySet, Sum

from .models import CreditDebitNote, InvoiceAuditLog, InvoiceHeader


def sales_summary(start: date, end: date, *, tenant=None) -> QuerySet:
    qs = InvoiceHeader.objects.filter(invoice_date__range=(start, end))
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.values("invoice_date", "customer_name").annotate(
        taxable=Sum("taxable_amount"), vat=Sum("vat_amount"), total=Sum("total_amount")
    )


def audit_log_report(start: date, end: date, *, user=None) -> QuerySet:
    qs = InvoiceAuditLog.objects.filter(timestamp__date__range=(start, end))
    if user:
        qs = qs.filter(user=user)
    return qs.select_related("invoice", "user")


def cbms_sync_report() -> QuerySet:
    return InvoiceHeader.objects.filter(sync_status__in=["pending", "failed"]).select_related("tenant")


def notes_report(*, tenant=None) -> QuerySet:
    qs = CreditDebitNote.objects.select_related("invoice")
    if tenant:
        qs = qs.filter(invoice__tenant=tenant)
    return qs


def queryset_to_csv(qs: Iterable, fields: Tuple[str, ...]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    for obj in qs:
        writer.writerow([getattr(obj, f, "") for f in fields])
    return buf.getvalue()


def dataframe_to_excel(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:  # type: ignore
        df.to_excel(writer, index=False)
    return buf.getvalue()
