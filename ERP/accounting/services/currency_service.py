"""
Currency resolution service for journal entries.

Provides functions to resolve exchange rates for currency setup in journal entries.
"""

import logging
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.core.exceptions import ValidationError

from accounting.services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)


def resolvecurrency(organization, from_currency: str, to_currency: str, rate_date) -> Decimal:
    """
    Resolve exchange rate for given currencies and date.

    Args:
        organization: Organization instance
        from_currency: Source currency code (transaction currency)
        to_currency: Target currency code (base currency)
        rate_date: Date for which to find the exchange rate

    Returns:
        Decimal: Exchange rate, defaults to 1.0 if not found or same currencies

    Raises:
        ValidationError: If rate lookup fails (but we catch and default)
    """
    if not from_currency or not to_currency or from_currency == to_currency:
        return Decimal('1.000000')

    # Create cache key for performance
    cache_key = f"exchange_rate_{organization.id}_{from_currency}_{to_currency}_{rate_date.isoformat()}"
    
    # Try to get from cache first
    cached_rate = cache.get(cache_key)
    if cached_rate is not None:
        return cached_rate

    try:
        service = ExchangeRateService(organization)
        quote = service.get_rate(from_currency, to_currency, rate_date)
        rate = quote.rate.quantize(Decimal('0.000001'))
        
        # Validate rate is positive
        if rate <= 0:
            raise ValidationError("Exchange rate must be positive")
            
        # Cache the result for 1 hour (3600 seconds)
        cache.set(cache_key, rate, 3600)
        logger.debug(f"Resolved exchange rate for {organization.name}: {from_currency}/{to_currency} on {rate_date} = {rate} (source: {quote.source})")
        return rate
    except ValidationError:
        # If no rate found or invalid rate, default to 1.0
        default_rate = Decimal('1.000000')
        # Cache the default for a shorter time (5 minutes)
        cache.set(cache_key, default_rate, 300)
        logger.info(f"No exchange rate found for {organization.name}: {from_currency}/{to_currency} on {rate_date}, using default {default_rate}")
        return default_rate