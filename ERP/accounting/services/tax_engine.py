"""Lightweight tax engine scaffold for dynamic tax selection and calculation."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Optional, Sequence

from django.db.models import Q
from django.utils import timezone

from ..models import TaxCode, TaxRule


@dataclass
class TaxContext:
    """Context used to resolve applicable taxes."""

    organization: object
    entry_mode: Optional[str] = None  # "sale", "purchase", "journal"
    country_code: Optional[str] = None
    state_code: Optional[str] = None
    city: Optional[str] = None
    product_category: Optional[str] = None
    customer_type: Optional[str] = None
    vendor_type: Optional[str] = None
    industry_code: Optional[str] = None
    transaction_date: Optional[date] = None


def _is_code_effective(code: TaxCode, txn_date: date) -> bool:
    """Guard against expired/not-yet-active codes."""
    if not txn_date:
        return True
    if code.effective_from and code.effective_from > txn_date:
        return False
    if code.effective_to and code.effective_to < txn_date:
        return False
    return True


def _rate_for(code: TaxCode) -> Decimal:
    """Prefer tax_rate, fall back to rate."""
    return Decimal(code.tax_rate or code.rate or 0)


def resolve_applicable_taxes(context: TaxContext) -> List[TaxCode]:
    """
    Return ordered, de-duplicated tax codes applicable to the given context.
    Rules with more specific matches should be ordered first via priority.
    """
    txn_date = context.transaction_date or timezone.now().date()
    qs = TaxRule.objects.filter(
        organization=context.organization,
        is_active=True,
    ).filter(
        Q(effective_from__isnull=True) | Q(effective_from__lte=txn_date),
        Q(effective_to__isnull=True) | Q(effective_to__gte=txn_date),
    )

    def _wildcard(field: str, value: Optional[str]):
        if not value:
            return
        qs_local = Q(**{field: value})
        qs_blank = Q(**{f"{field}__isnull": True}) | Q(**{f"{field}": ""})
        return qs_local | qs_blank

    filters = [
        ('entry_mode', context.entry_mode),
        ('country_code', context.country_code),
        ('state_code', context.state_code),
        ('city', context.city),
        ('product_category', context.product_category),
        ('customer_type', context.customer_type),
        ('vendor_type', context.vendor_type),
        ('industry_code', context.industry_code),
    ]
    for field, value in filters:
        clause = _wildcard(field, value)
        if clause is not None:
            qs = qs.filter(clause)

    rules = qs.order_by('priority', 'tax_rule_id').prefetch_related('tax_codes', 'tax_code_group__tax_codes')

    seen = set()
    ordered_codes: List[TaxCode] = []
    for rule in rules:
        candidates = list(rule.tax_codes.all())
        if rule.tax_code_group:
            candidates.extend(list(rule.tax_code_group.tax_codes.all()))

        for code in candidates:
            if not _is_code_effective(code, txn_date):
                continue
            if code.pk in seen:
                continue
            seen.add(code.pk)
            ordered_codes.append(code)

    return ordered_codes


def calculate_line_taxes(
    base_amount: Decimal,
    tax_codes: Sequence[TaxCode],
    transaction_date: Optional[date] = None,
) -> List[dict]:
    """
    Given a base amount and an ordered list of tax codes, calculate taxes.
    Compound taxes apply on top of prior tax totals.
    Returns list of dicts suitable for InvoiceLineTax creation.
    """
    txn_date = transaction_date or timezone.now().date()
    total_prior_taxes = Decimal('0')
    breakdown: List[dict] = []

    for sequence, code in enumerate(tax_codes, start=1):
        if not _is_code_effective(code, txn_date):
            continue
        rate = _rate_for(code)
        taxable_base = base_amount + total_prior_taxes if code.is_compound else base_amount
        tax_amount = (taxable_base * rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_prior_taxes += tax_amount
        breakdown.append(
            {
                "tax_code": code,
                "sequence": sequence,
                "base_amount": taxable_base,
                "tax_amount": tax_amount,
            }
        )

    return breakdown

