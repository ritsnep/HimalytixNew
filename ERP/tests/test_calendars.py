import datetime

import pytest
from django.core import mail
import django.core.mail.backends.locmem  # noqa: F401 - ensures mail.outbox is defined

from utils.calendars import (
    ad_to_bs_string,
    bs_to_ad_string,
    maybe_coerce_bs_date,
)
from utils.widgets import DualCalendarWidget

pytestmark = pytest.mark.django_db(transaction=True)


def test_bs_to_ad_and_back_round_trip():
    bs = "2077-05-19"  # Known mapping from library docs -> 2020-09-04
    ad_iso = bs_to_ad_string(bs)
    assert ad_iso == "2020-09-04"

    bs_iso = ad_to_bs_string(ad_iso)
    assert bs_iso == bs


def test_maybe_coerce_bs_handles_nepali_digits():
    # Use Nepali digits and slashes; should normalize and convert.
    bs_nepali = "२०७७/०५/१९"
    coerced = maybe_coerce_bs_date(bs_nepali)
    assert coerced == datetime.date(2020, 9, 4)


def test_dual_calendar_widget_falls_back_to_bs_value_when_ad_missing():
    widget = DualCalendarWidget()
    data = {"journal_date_bs": "2077-05-19"}
    resolved = widget.value_from_datadict(data, files={}, name="journal_date")
    assert resolved == "2020-09-04"
