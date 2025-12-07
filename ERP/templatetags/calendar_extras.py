from django import template

from utils.calendars import CalendarMode, ad_to_bs_string

register = template.Library()


@register.filter
def to_bs(value):
    """
    Convert an AD date/datetime/string to a BS YYYY-MM-DD string.
    Returns an empty string when conversion fails.
    """
    return ad_to_bs_string(value) or ""


@register.simple_tag
def dual_date(value, mode: str = CalendarMode.AD):
    """
    Render a date in the preferred calendar mode.

    - AD: returns ISO AD string
    - BS: returns BS string (falls back to AD)
    - DUAL: returns "AD (BS)" when BS is available
    """
    ad_value = ""
    if hasattr(value, "isoformat"):
        try:
            ad_value = value.isoformat()
        except Exception:
            ad_value = ""
    elif isinstance(value, str):
        ad_value = value

    bs_value = ad_to_bs_string(value) or ""
    mode = (mode or CalendarMode.AD).upper()

    if mode == CalendarMode.BS:
        return bs_value or ad_value
    if mode == CalendarMode.DUAL:
        if bs_value and ad_value:
            return f"{ad_value} ({bs_value})"
        return bs_value or ad_value
    return ad_value or bs_value
