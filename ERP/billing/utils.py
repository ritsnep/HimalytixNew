from decimal import Decimal
from typing import Tuple

from billing.models import quantize_amount


def compute_vat_and_total(taxable_amount: Decimal, vat_rate: Decimal) -> Tuple[Decimal, Decimal]:
    """Return (vat_amount, total_amount) using standard rounding."""
    taxable = quantize_amount(taxable_amount or Decimal("0"))
    rate = (vat_rate or Decimal("0")) / Decimal("100")
    vat_amount = quantize_amount(taxable * rate)
    total_amount = quantize_amount(taxable + vat_amount)
    return vat_amount, total_amount
