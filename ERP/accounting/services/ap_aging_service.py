from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, List

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounting.models import Organization, PurchaseInvoice


@dataclass
class VendorAgingRow:
    vendor_id: int
    vendor_name: str
    buckets: OrderedDict
    total: Decimal


class APAgingService:
    """Calculates AP aging by vendor based on outstanding purchase invoices."""

    DEFAULT_BUCKETS = [30, 60, 90]
    OPEN_STATUSES = ('validated', 'matched', 'ready_for_posting', 'posted')

    def __init__(
        self,
        organization: Organization,
        reference_date: date | None = None,
        bucket_days: Iterable[int] | None = None,
    ):
        self.organization = organization
        self.reference_date = reference_date or timezone.now().date()
        self.bucket_days = sorted(bucket_days or self.DEFAULT_BUCKETS)

    def _empty_bucket_map(self) -> OrderedDict:
        buckets = OrderedDict()
        buckets['current'] = Decimal('0')
        previous = 0
        for bucket in self.bucket_days:
            start = previous + 1
            label = f"{start:02d}-{bucket}"
            buckets[label] = Decimal('0')
            previous = bucket
        buckets[f">{self.bucket_days[-1]}"] = Decimal('0')
        return buckets

    def _bucket_label(self, due_date: date) -> str:
        days_past_due = (self.reference_date - due_date).days
        if days_past_due <= 0:
            return 'current'
        previous = 0
        for bucket in self.bucket_days:
            if days_past_due <= bucket:
                start = previous + 1
                return f"{start:02d}-{bucket}"
            previous = bucket
        return f">{self.bucket_days[-1]}"

    def bucket_labels(self) -> list[str]:
        """Return the ordered bucket labels used by this service."""
        return list(self._empty_bucket_map().keys())

    def _outstanding_amount(self, invoice) -> Decimal:
        return (invoice.total or Decimal('0')) - (
            (invoice.paid_amount or Decimal('0')) + (invoice.discount_amount or Decimal('0'))
        )

    def build(self) -> List[VendorAgingRow]:
        invoices = (
            PurchaseInvoice.objects.filter(
                organization=self.organization,
                status__in=self.OPEN_STATUSES,
            )
            .select_related('vendor')
            .annotate(
                paid_amount=Coalesce(Sum('payment_lines__applied_amount'), Decimal('0')),
                discount_amount=Coalesce(Sum('payment_lines__discount_taken'), Decimal('0')),
            )
        )

        vendor_map: dict[int, VendorAgingRow] = {}
        for invoice in invoices:
            outstanding = self._outstanding_amount(invoice)
            if outstanding <= 0:
                continue
            label = self._bucket_label(invoice.due_date)
            vendor_id = invoice.vendor_id
            row = vendor_map.get(vendor_id)
            if row is None:
                row = VendorAgingRow(
                    vendor_id=vendor_id,
                    vendor_name=invoice.vendor.display_name,
                    buckets=self._empty_bucket_map(),
                    total=Decimal('0'),
                )
                vendor_map[vendor_id] = row
            row.buckets[label] += outstanding
            row.total += outstanding

        return sorted(vendor_map.values(), key=lambda r: r.vendor_name.lower())

    def summarize(self) -> OrderedDict:
        summary = self._empty_bucket_map()
        rows = self.build()
        for row in rows:
            for label, amount in row.buckets.items():
                summary[label] += amount
        summary['grand_total'] = sum(summary.values(), Decimal('0'))
        return summary
