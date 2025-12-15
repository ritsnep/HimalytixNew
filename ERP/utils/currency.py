"""
Currency Management Utilities

Provides comprehensive currency handling including conversion, formatting,
exchange rates, and multi-currency operations for the accounting system.
"""

from typing import Optional, Dict, List, Any, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP
from django.db import models, transaction
from django.core.cache import cache
from django.utils import timezone
from django.core.exceptions import ValidationError

from .organization import OrganizationService
from usermanagement.models import Organization


class CurrencyConverter:
    """
    Handles currency conversion operations with exchange rate management.
    """

    CACHE_KEY_PREFIX = "currency_rate"
    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def convert_amount(
        amount: Decimal,
        from_currency: Union[str, Any],
        to_currency: Union[str, Any],
        date: Optional[Any] = None,
        rate: Optional[Decimal] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Convert amount between currencies.

        Args:
            amount: Amount to convert
            from_currency: Source currency (code or object)
            to_currency: Target currency (code or object)
            date: Date for exchange rate (defaults to latest)
            rate: Specific exchange rate to use (optional)

        Returns:
            Tuple of (converted_amount, exchange_rate_used)

        Usage:
            # Convert USD to NPR
            converted, rate = CurrencyConverter.convert_amount(
                Decimal('100'), 'USD', 'NPR', date.today()
            )
        """
        if amount is None or amount == 0:
            return Decimal('0'), Decimal('1')

        from_code = CurrencyConverter._get_currency_code(from_currency)
        to_code = CurrencyConverter._get_currency_code(to_currency)

        if from_code == to_code:
            return amount, Decimal('1')

        if rate is None:
            rate = CurrencyConverter.get_exchange_rate(from_code, to_code, date)

        if rate is None:
            raise ValueError(f"No exchange rate available for {from_code} to {to_code}")

        converted = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return converted, rate

    @staticmethod
    def get_exchange_rate(
        from_currency: str,
        to_currency: str,
        date: Optional[Any] = None,
        organization: Optional[Organization] = None
    ) -> Optional[Decimal]:
        """
        Get exchange rate between two currencies.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            date: Date for rate (defaults to latest)
            organization: Organization for filtering

        Returns:
            Exchange rate or None if not found

        Usage:
            # Get latest USD to NPR rate
            rate = CurrencyConverter.get_exchange_rate('USD', 'NPR')
        """
        if from_currency == to_currency:
            return Decimal('1')

        # Try cache first
        cache_key = CurrencyConverter._get_cache_key(from_currency, to_currency, date, organization)
        cached_rate = cache.get(cache_key)
        if cached_rate is not None:
            return Decimal(str(cached_rate)) if cached_rate else None

        # Query database
        rate = CurrencyConverter._query_exchange_rate(from_currency, to_currency, date, organization)

        # Cache result
        cache.set(cache_key, str(rate) if rate else None, CurrencyConverter.CACHE_TIMEOUT)

        return rate

    @staticmethod
    def _query_exchange_rate(
        from_code: str,
        to_code: str,
        date: Optional[Any] = None,
        organization: Optional[Organization] = None
    ) -> Optional[Decimal]:
        """Query exchange rate from database."""
        from accounting.models import CurrencyExchangeRate

        queryset = CurrencyExchangeRate.objects.filter(
            from_currency__currency_code=from_code,
            to_currency__currency_code=to_code,
            is_active=True
        )

        if organization:
            queryset = OrganizationService.filter_queryset_by_org(queryset, organization)

        if date:
            # Get rate for specific date or closest before
            rate_obj = queryset.filter(rate_date__lte=date).order_by('-rate_date').first()
        else:
            # Get latest rate
            rate_obj = queryset.order_by('-rate_date').first()

        return rate_obj.exchange_rate if rate_obj else None

    @staticmethod
    def _get_cache_key(from_curr: str, to_curr: str, date: Optional[Any], org: Optional[Organization]) -> str:
        """Generate cache key for exchange rate."""
        date_str = date.isoformat() if date else 'latest'
        org_id = org.pk if org else 'global'
        return f"{CurrencyConverter.CACHE_KEY_PREFIX}:{from_curr}:{to_curr}:{date_str}:{org_id}"

    @staticmethod
    def _get_currency_code(currency: Union[str, Any]) -> str:
        """Extract currency code from string or object."""
        if isinstance(currency, str):
            return currency.upper()
        elif hasattr(currency, 'currency_code'):
            return currency.currency_code.upper()
        elif hasattr(currency, 'code'):
            return currency.code.upper()
        else:
            raise ValueError(f"Invalid currency format: {currency}")

    @staticmethod
    def invalidate_cache(
        from_currency: Optional[str] = None,
        to_currency: Optional[str] = None,
        organization: Optional[Organization] = None
    ) -> None:
        """
        Invalidate exchange rate cache.

        Args:
            from_currency: Specific from currency to invalidate (optional)
            to_currency: Specific to currency to invalidate (optional)
            organization: Specific organization to invalidate (optional)

        Usage:
            # Clear all cache
            CurrencyConverter.invalidate_cache()

            # Clear specific pair
            CurrencyConverter.invalidate_cache('USD', 'NPR')
        """
        pattern = f"{CurrencyConverter.CACHE_KEY_PREFIX}:"
        if from_currency and to_currency:
            pattern += f"{from_currency}:{to_currency}:*"
        elif from_currency:
            pattern += f"{from_currency}:*:*"
        elif to_currency:
            pattern += f"*:{to_currency}:*"
        else:
            pattern += "*"

        # Note: This is a simplified invalidation. In production, you might want
        # to use a more sophisticated cache invalidation strategy
        cache.delete_pattern(pattern) if hasattr(cache, 'delete_pattern') else None


class CurrencyFormatter:
    """
    Handles currency formatting and display operations.
    """

    @staticmethod
    def format_amount(
        amount: Union[Decimal, float, int],
        currency: Union[str, Any],
        locale: str = 'en',
        show_symbol: bool = True,
        decimals: Optional[int] = None
    ) -> str:
        """
        Format currency amount with proper locale and symbol.

        Args:
            amount: Amount to format
            currency: Currency code or object
            locale: Locale for formatting ('en', 'ne', etc.)
            show_symbol: Whether to include currency symbol
            decimals: Decimal places (auto-detect if None)

        Returns:
            Formatted currency string

        Usage:
            # Format USD amount
            formatted = CurrencyFormatter.format_amount(Decimal('1234.56'), 'USD')
            # Output: "$1,234.56"
        """
        if amount is None:
            amount = Decimal('0')

        amount = Decimal(str(amount))
        currency_code = CurrencyConverter._get_currency_code(currency)

        # Get currency info
        currency_info = CurrencyFormatter._get_currency_info(currency_code)
        symbol = currency_info.get('symbol', currency_code) if show_symbol else ''

        # Determine decimal places
        if decimals is None:
            decimals = currency_info.get('decimal_places', 2)

        # Format based on locale
        if locale == 'ne':  # Nepali locale
            formatted = CurrencyFormatter._format_nepali(amount, decimals)
        else:  # Default English formatting
            formatted = CurrencyFormatter._format_english(amount, decimals)

        # Add symbol based on locale convention
        if show_symbol:
            if locale == 'ne':
                # Symbol after amount in Nepali
                formatted = f"{formatted} {symbol}"
            else:
                # Symbol before amount in English
                formatted = f"{symbol}{formatted}"

        return formatted

    @staticmethod
    def _get_currency_info(currency_code: str) -> Dict[str, Any]:
        """Get currency information."""
        # This could be loaded from a currency config or database
        CURRENCY_INFO = {
            'USD': {'symbol': '$', 'decimal_places': 2, 'name': 'US Dollar'},
            'EUR': {'symbol': '€', 'decimal_places': 2, 'name': 'Euro'},
            'GBP': {'symbol': '£', 'decimal_places': 2, 'name': 'British Pound'},
            'JPY': {'symbol': '¥', 'decimal_places': 0, 'name': 'Japanese Yen'},
            'NPR': {'symbol': '₨', 'decimal_places': 2, 'name': 'Nepalese Rupee'},
            'INR': {'symbol': '₹', 'decimal_places': 2, 'name': 'Indian Rupee'},
        }
        return CURRENCY_INFO.get(currency_code.upper(), {'symbol': currency_code, 'decimal_places': 2})

    @staticmethod
    def _format_english(amount: Decimal, decimals: int) -> str:
        """Format amount in English locale."""
        # Convert to string with proper decimals
        formatted = f"{amount:.{decimals}f}"

        # Add thousand separators
        parts = formatted.split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else ''

        # Add commas for thousands
        integer_formatted = ""
        for i, char in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                integer_formatted = ',' + integer_formatted
            integer_formatted = char + integer_formatted

        if decimal_part:
            return f"{integer_formatted}.{decimal_part}"
        return integer_formatted

    @staticmethod
    def _format_nepali(amount: Decimal, decimals: int) -> str:
        """Format amount in Nepali locale."""
        # For Nepali, we might want to use Nepali numerals
        # This is a simplified implementation
        formatted = f"{amount:.{decimals}f}"

        # Convert Arabic numerals to Nepali if needed
        # This would require additional Nepali numeral conversion logic
        return formatted


class MultiCurrencyCalculator:
    """
    Handles multi-currency calculations and balance conversions.
    """

    @staticmethod
    def calculate_base_amount(
        amount: Decimal,
        currency_code: str,
        base_currency: str,
        exchange_rate: Optional[Decimal] = None,
        date: Optional[Any] = None,
        organization: Optional[Organization] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate amount in base currency.

        Args:
            amount: Amount in transaction currency
            currency_code: Transaction currency code
            base_currency: Base currency code
            exchange_rate: Specific exchange rate (optional)
            date: Date for rate lookup
            organization: Organization for rate filtering

        Returns:
            Tuple of (base_amount, exchange_rate_used)

        Usage:
            # Calculate base amount for transaction
            base_amount, rate = MultiCurrencyCalculator.calculate_base_amount(
                Decimal('100'), 'USD', 'NPR', organization=request.organization
            )
        """
        if currency_code == base_currency:
            return amount, Decimal('1')

        if exchange_rate is None:
            exchange_rate = CurrencyConverter.get_exchange_rate(
                currency_code, base_currency, date, organization
            )

        if exchange_rate is None:
            raise ValueError(f"No exchange rate for {currency_code} to {base_currency}")

        base_amount = (amount * exchange_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return base_amount, exchange_rate

    @staticmethod
    def calculate_transaction_amount(
        base_amount: Decimal,
        currency_code: str,
        base_currency: str,
        exchange_rate: Optional[Decimal] = None,
        date: Optional[Any] = None,
        organization: Optional[Organization] = None
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate amount in transaction currency from base currency.

        Args:
            base_amount: Amount in base currency
            currency_code: Target transaction currency
            base_currency: Base currency code
            exchange_rate: Specific exchange rate (optional)
            date: Date for rate lookup
            organization: Organization for rate filtering

        Returns:
            Tuple of (transaction_amount, exchange_rate_used)
        """
        if currency_code == base_currency:
            return base_amount, Decimal('1')

        if exchange_rate is None:
            # Need inverse rate
            rate = CurrencyConverter.get_exchange_rate(
                currency_code, base_currency, date, organization
            )
            if rate:
                exchange_rate = Decimal('1') / rate

        if exchange_rate is None:
            raise ValueError(f"No exchange rate for {currency_code} to {base_currency}")

        transaction_amount = (base_amount * exchange_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return transaction_amount, exchange_rate


class CurrencyValidator:
    """
    Validation utilities for currency operations.
    """

    @staticmethod
    def validate_currency_code(code: str) -> bool:
        """Validate currency code format (3 uppercase letters)."""
        import re
        return bool(re.match(r'^[A-Z]{3}$', code))

    @staticmethod
    def validate_exchange_rate(rate: Decimal) -> Tuple[bool, str]:
        """Validate exchange rate value."""
        if rate is None:
            return False, "Exchange rate is required"

        if rate <= 0:
            return False, "Exchange rate must be positive"

        if rate > 1000000:  # Arbitrary upper limit
            return False, "Exchange rate seems unreasonably high"

        return True, ""

    @staticmethod
    def validate_currency_conversion(
        from_currency: str,
        to_currency: str,
        amount: Decimal,
        organization: Optional[Organization] = None
    ) -> Tuple[bool, str]:
        """Validate currency conversion is possible."""
        if not amount or amount == 0:
            return True, ""  # Zero amounts are always valid

        if from_currency == to_currency:
            return True, ""

        # Check if currencies exist
        from accounting.models import Currency
        from_curr_obj = Currency.objects.filter(currency_code=from_currency).first()
        to_curr_obj = Currency.objects.filter(currency_code=to_currency).first()

        if not from_curr_obj:
            return False, f"Source currency {from_currency} does not exist"

        if not to_curr_obj:
            return False, f"Target currency {to_currency} does not exist"

        # Check if exchange rate exists
        rate = CurrencyConverter.get_exchange_rate(from_currency, to_currency, None, organization)
        if rate is None:
            return False, f"No exchange rate available for {from_currency} to {to_currency}"

        return True, ""


# Template widget for currency input
class CurrencyInputWidget:
    """
    Template widget for currency amount input with formatting.
    """

    template_name = "widgets/currency_input.html"

    def __init__(self, currency: Optional[Any] = None, **kwargs):
        self.currency = currency
        self.attrs = kwargs

    def get_context(self, name: str, value: Any, attrs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get context for template rendering."""
        currency_code = CurrencyConverter._get_currency_code(self.currency) if self.currency else 'USD'
        currency_info = CurrencyFormatter._get_currency_info(currency_code)

        context = {
            'name': name,
            'value': value or '',
            'currency_code': currency_code,
            'currency_symbol': currency_info.get('symbol', currency_code),
            'decimal_places': currency_info.get('decimal_places', 2),
            'attrs': attrs or {},
        }
        return context
