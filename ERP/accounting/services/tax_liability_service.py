from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Iterable, List

from django.db import transaction
from django.db.models import Sum

from accounting.models import (
    PurchaseInvoice,
    SalesInvoice,
    TaxLiability,
    TaxCode,
    AccountingSettings,
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
        period_start = self._period_key(period_start)
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

    def build_vat_summary(self, period_start: date) -> Dict[str, Any]:
        period_start = self._period_key(period_start)
        period_end = self._end_of_month(period_start)
        buckets = self.aggregate(period_start)
        total_input = Decimal('0')
        total_output = Decimal('0')
        lines: List[Dict[str, Any]] = []
        for bucket in buckets:
            input_tax = bucket.payable
            output_tax = bucket.receivable
            net_balance = input_tax - output_tax
            direction = 'refund' if net_balance > 0 else 'payable' if net_balance < 0 else 'even'
            lines.append(
                {
                    'tax_code': bucket.tax_code.code,
                    'tax_code_name': bucket.tax_code.name,
                    'tax_type_code': bucket.tax_code.tax_type.code if bucket.tax_code.tax_type else None,
                    'tax_type_name': bucket.tax_code.tax_type.name if bucket.tax_code.tax_type else None,
                    'report_line_code': bucket.tax_code.report_line_code,
                    'input_tax': input_tax,
                    'output_tax': output_tax,
                    'net_balance': net_balance,
                    'direction': direction,
                }
            )
            total_input += input_tax
            total_output += output_tax
        net_balance = total_input - total_output
        return {
            'period_start': period_start,
            'period_end': period_end,
            'total_input_tax': total_input,
            'total_output_tax': total_output,
            'net_balance': net_balance,
            'lines': lines,
        }

    def build_nfrs_schedule(self, period_start: date) -> Dict[str, Any]:
        period_start = self._period_key(period_start)
        period_end = self._end_of_month(period_start)
        buckets = self.aggregate(period_start)
        framework = getattr(
            getattr(self.organization, 'accounting_settings', None),
            'statutory_framework',
            AccountingSettings.IFRS,
        )
        assets: List[Dict[str, Any]] = []
        liabilities: List[Dict[str, Any]] = []
        total_assets = Decimal('0')
        total_liabilities = Decimal('0')
        for bucket in buckets:
            net_balance = bucket.payable - bucket.receivable
            base_row = {
                'tax_code': bucket.tax_code.code,
                'tax_code_name': bucket.tax_code.name,
                'line_code': bucket.tax_code.report_line_code or bucket.tax_code.code,
                'tax_type_code': bucket.tax_code.tax_type.code if bucket.tax_code.tax_type else None,
                'tax_type_name': bucket.tax_code.tax_type.name if bucket.tax_code.tax_type else None,
                'net_balance': net_balance,
            }
            if net_balance > 0:
                assets.append({**base_row, 'balance': net_balance})
                total_assets += net_balance
            elif net_balance < 0:
                liabilities.append({**base_row, 'balance': abs(net_balance)})
                total_liabilities += abs(net_balance)
        return {
            'framework': framework,
            'period_start': period_start,
            'period_end': period_end,
            'assets': assets,
            'liabilities': liabilities,
            'totals': {
                'asset_balance': total_assets,
                'liability_balance': total_liabilities,
            },
        }

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
