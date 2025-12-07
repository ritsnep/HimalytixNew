import datetime
from typing import Optional, Sequence, Union

import nepali_datetime
from django.utils.dateparse import parse_date


DateLike = Union[str, datetime.date, datetime.datetime]

# Map Nepali numerals to ASCII for tolerant parsing.
_NEPALI_DIGIT_MAP = str.maketrans("०१२३४५६७८९", "0123456789")


class CalendarMode:
    """Supported calendar presentation modes."""

    AD = "AD"
    BS = "BS"
    DUAL = "DUAL"
    DEFAULT = AD

    @classmethod
    def choices(cls):
        return (
            (cls.AD, "Gregorian (AD only)"),
            (cls.BS, "Bikram Sambat (BS only)"),
            (cls.DUAL, "Dual (toggle AD/BS)"),
        )

    @classmethod
    def normalize(cls, value: Optional[str]) -> str:
        if not value:
            return cls.DEFAULT
        normalized = str(value).upper()
        return normalized if normalized in {cls.AD, cls.BS, cls.DUAL} else cls.DEFAULT


def _ensure_date(value: DateLike) -> Optional[datetime.date]:
    """Coerce common date inputs to a date object."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        parsed = parse_date(value.strip())
        return parsed
    return None


def _normalize_bs_string(value: str) -> str:
    """Standardize separators and numerals for BS strings."""
    return value.strip().replace("/", "-").translate(_NEPALI_DIGIT_MAP)


def _split_bs(value: str) -> Optional[tuple[int, int, int]]:
    """Split a BS string into (year, month, day) ints."""
    if not value:
        return None
    parts = _normalize_bs_string(value).split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(p) for p in parts)
    except (TypeError, ValueError):
        return None
    return year, month, day


def bs_to_ad(bs_value: Union[str, Sequence[int]]) -> Optional[datetime.date]:
    """Convert a Bikram Sambat date (string or Y-M-D sequence) to a Gregorian date."""
    if isinstance(bs_value, (list, tuple)) and len(bs_value) == 3:
        year, month, day = bs_value
    else:
        components = _split_bs(str(bs_value)) if bs_value is not None else None
        if not components:
            return None
        year, month, day = components

    try:
        return nepali_datetime.date(year, month, day).to_datetime_date()
    except Exception:
        return None


def bs_to_ad_string(bs_value: Union[str, Sequence[int]]) -> Optional[str]:
    """Convert BS input to ISO AD string."""
    converted = bs_to_ad(bs_value)
    return converted.isoformat() if converted else None


def ad_to_bs(ad_value: DateLike) -> Optional[nepali_datetime.date]:
    """Convert a Gregorian date/datetime/ISO string to a Nepali date."""
    date_obj = _ensure_date(ad_value)
    if not date_obj:
        return None
    try:
        return nepali_datetime.date.from_datetime_date(date_obj)
    except Exception:
        return None


def ad_to_bs_string(ad_value: DateLike) -> Optional[str]:
    """Convert AD date input to a YYYY-MM-DD BS string."""
    bs_date = ad_to_bs(ad_value)
    return bs_date.strftime("%Y-%m-%d") if bs_date else None


def is_probable_bs_year(year: int) -> bool:
    """Heuristic: BS years start around 2000; anything 1900-2100 is likely AD."""
    return year >= 2000


def maybe_coerce_bs_date(value: str) -> Optional[datetime.date]:
    """
    Try converting a date string that looks like BS into AD.

    Intended as a server-side safety net if the browser submits the BS field.
    """
    normalized = _normalize_bs_string(value or "")
    parts = normalized.split("-")
    if len(parts) != 3:
        return None
    try:
        year = int(parts[0])
    except ValueError:
        return None
    if not is_probable_bs_year(year):
        return None
    return bs_to_ad(normalized)


def get_calendar_mode(source=None, default: str = CalendarMode.DEFAULT) -> str:
    """
    Resolve the calendar mode from various sources (model, dict, settings-like object).

    Accepts:
    - An object with a `calendar_mode` attribute
    - A mapping with `calendar_mode` key
    - None, which yields the provided default
    """
    default = CalendarMode.normalize(default)
    if source is None:
        return default

    candidate = None
    if hasattr(source, "calendar_mode"):
        candidate = getattr(source, "calendar_mode", None)
    elif isinstance(source, dict):
        candidate = source.get("calendar_mode")
    elif hasattr(source, "config"):
        candidate = getattr(getattr(source, "config", None), "calendar_mode", None)

    return CalendarMode.normalize(candidate) or default


class DateSeedStrategy:
    """How date inputs should pre-populate."""

    TODAY = "TODAY"
    LAST_OR_TODAY = "LAST_OR_TODAY"
    DEFAULT = LAST_OR_TODAY

    @classmethod
    def choices(cls):
        return (
            (cls.TODAY, "Always today"),
            (cls.LAST_OR_TODAY, "Last entry or today"),
        )

    @classmethod
    def normalize(cls, value: Optional[str]) -> str:
        if not value:
            return cls.DEFAULT
        normalized = str(value).upper()
        return normalized if normalized in {cls.TODAY, cls.LAST_OR_TODAY} else cls.DEFAULT
