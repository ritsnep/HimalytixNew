from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.db.models import Sum

from accounting.models import (
    PurchaseInvoice,
    SalesInvoice,
    TaxLiability,
    TaxCode,
)


@dataclass
class TaxBucket:
    tax_code: TaxCode
    period_start: date
    period_end: date
    payable: Decimal = Decimal('0')
    receivable: Decimal = Decimal('0')


class TaxLiabilityService:
    """Aggregates tax data across invoices for reporting/filing."""

    def __init__(self, organization):
        self.organization = organization

    def _period_key(self, item_date: date):
        return date(item_date.year, item_date.month, 1)

    def _get_range(self, period_start: date):
        return period_start, self._end_of_month(period_start)

    def _end_of_month(self, start: date):
        import calendar

        last_day = calendar.monthrange(start.year, start.month)[1]
        return date(start.year, start.month, last_day)

    def aggregate(self, period_start: date) -> Iterable[TaxBucket]:
        period_end = self._end_of_month(period_start)
        purchase_tax = (
            PurchaseInvoice.objects.filter(
                organization=self.organization,
                invoice_date__gte=period_start,
                invoice_date__lte=period_end,
                status__in=['posted', 'matched', 'ready_for_posting'],
                lines__tax_code__isnull=False,
            )
            .values('lines__tax_code')
            .annotate(total=Sum('lines__tax_amount'))
        )
        sales_tax = (
            SalesInvoice.objects.filter(
                organization=self.organization,
                invoice_date__gte=period_start,
                invoice_date__lte=period_end,
                status__in=['posted', 'validated'],
                lines__tax_code__isnull=False,
            )
            .values('lines__tax_code')
            .annotate(total=Sum('lines__tax_amount'))
        )

        buckets: dict[int, TaxBucket] = {}
        for entry in purchase_tax:
            tax_code_id = entry['lines__tax_code']
            bucket = buckets.setdefault(
                tax_code_id,
                TaxBucket(
                    tax_code=TaxCode.objects.get(pk=tax_code_id),
                    period_start=period_start,
                    period_end=period_end,
                ),
            )
            bucket.payable += Decimal(entry['total'] or 0)
        for entry in sales_tax:
            tax_code_id = entry['lines__tax_code']
            bucket = buckets.setdefault(
                tax_code_id,
                TaxBucket(
                    tax_code=TaxCode.objects.get(pk=tax_code_id),
                    period_start=period_start,
                    period_end=period_end,
                ),
            )
            bucket.receivable += Decimal(entry['total'] or 0)
        return list(buckets.values())

    @transaction.atomic
    def record_liabilities(self, period_start: date):
        buckets = self.aggregate(period_start)
        for bucket in buckets:
            net = bucket.payable - bucket.receivable
            obj, created = TaxLiability.objects.update_or_create(
                organization=self.organization,
                tax_code=bucket.tax_code,
                period_start=bucket.period_start,
                period_end=bucket.period_end,
                defaults={
                    'amount': net,
                    'status': 'pending',
                },
            )
            obj.metadata['payable'] = str(bucket.payable)
            obj.metadata['receivable'] = str(bucket.receivable)
            obj.save()
