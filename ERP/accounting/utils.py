from contextlib import contextmanager

_thread_locals = {}

def get_current_request():
    return _thread_locals.get('request')

@contextmanager
def record_request(request):
    _thread_locals['request'] = request
    yield
    _thread_locals.pop('request', None)

def get_current_user():
    request = get_current_request()
    if request:
        return request.user
    return None

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


from decimal import Decimal
from django.db.models import Q

from .models import CurrencyExchangeRate, Currency


def _as_currency_code(c):
    if c is None:
        return None
    if isinstance(c, Currency):
        return c.currency_code
    # assume string-like
    return str(c)


def get_latest_exchange_rate(from_currency, to_currency, organization=None):
    """Return the most recent exchange rate (Decimal) converting from `from_currency` to `to_currency`.

    - `from_currency` and `to_currency` may be currency codes or `Currency` instances.
    - If currencies are equal, returns Decimal('1').
    - If no rate is found, returns None.
    """
    from_code = _as_currency_code(from_currency)
    to_code = _as_currency_code(to_currency)

    if not from_code or not to_code:
        return None

    if from_code == to_code:
        return Decimal('1')

    qs = CurrencyExchangeRate.objects.filter(
        from_currency_id=from_code,
        to_currency_id=to_code,
    )
    if organization is not None:
        qs = qs.filter(organization=organization)

    # Prefer most recent by rate_date then by pk
    rate = qs.order_by('-rate_date', '-pk').first()
    if rate:
        return rate.exchange_rate
    return None