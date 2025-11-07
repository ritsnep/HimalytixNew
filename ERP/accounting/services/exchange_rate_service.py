from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from django.core.exceptions import ValidationError

from accounting.models import CurrencyExchangeRate

if TYPE_CHECKING:  # pragma: no cover - import for type hints only
    from usermanagement.models import Organization


@dataclass
class ExchangeRateQuote:
    """Result of an exchange rate lookup."""

    rate: Decimal
    rate_date: date
    source: str
    used_inverse: bool = False


class ExchangeRateService:
    """Provides hydrated exchange rates for journal posting."""

    def __init__(self, organization: "Organization", allow_inverse_lookup: bool = True):
        self.organization = organization
        self.allow_inverse_lookup = allow_inverse_lookup

    def get_rate(self, from_currency: str, to_currency: str, rate_date: date) -> ExchangeRateQuote:
        if from_currency == to_currency:
            return ExchangeRateQuote(rate=Decimal("1"), rate_date=rate_date, source="identity")

        quote = self._direct_lookup(from_currency, to_currency, rate_date)
        if quote:
            return quote

        if self.allow_inverse_lookup:
            inverse = self._direct_lookup(to_currency, from_currency, rate_date)
            if inverse:
                if inverse.rate == 0:
                    raise ValidationError("Inverse exchange rate cannot be zero.")
                inverted = (Decimal("1") / inverse.rate).quantize(Decimal("0.000001"))
                return ExchangeRateQuote(
                    rate=inverted,
                    rate_date=inverse.rate_date,
                    source=f"inverse:{inverse.source}",
                    used_inverse=True,
                )

        raise ValidationError(
            f"No exchange rate configured for {from_currency}/{to_currency} on or before {rate_date}."
        )

    def _direct_lookup(self, from_currency: str, to_currency: str, rate_date: date) -> Optional[ExchangeRateQuote]:
        qs = (
            CurrencyExchangeRate.objects.filter(
                organization=self.organization,
                from_currency__currency_code=from_currency,
                to_currency__currency_code=to_currency,
                rate_date__lte=rate_date,
                is_active=True,
            )
            .order_by("-rate_date")
        )

        record = qs.first()
        if record:
            return ExchangeRateQuote(
                rate=Decimal(record.exchange_rate),
                rate_date=record.rate_date,
                source=record.source or "manual",
            )
        return None
