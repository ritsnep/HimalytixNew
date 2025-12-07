import datetime

from django import forms
from django.db import models
from django.utils import timezone

from utils.calendars import DateSeedStrategy
from utils.widgets import DualCalendarWidget, set_default_date_initial


def _stub_model(last_date=None, has_org=True):
    class DummyQS:
        def __init__(self, obj):
            self.obj = obj

        def all(self):
            return self

        def filter(self, **kwargs):
            return self

        def exclude(self, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def only(self, *args, **kwargs):
            return self

        def first(self):
            return self.obj

    org_field = type("F", (), {"name": "organization"})()
    date_field = models.DateField()
    date_field.name = "journal_date"

    class DummyMeta:
        fields = [org_field, date_field] if has_org else [date_field]

        def get_field(self, name):
            return date_field

    class DummyModel:
        _meta = DummyMeta()
        objects = DummyQS(last_date)

    return DummyModel


def test_dual_calendar_widget_defaults_to_today_when_empty(monkeypatch):
    today = datetime.date(2024, 1, 2)
    monkeypatch.setattr(timezone, "localdate", lambda: today)
    widget = DualCalendarWidget()
    ctx = widget.get_context("journal_date", value=None)
    assert ctx["widget"]["ad_value"] == today.isoformat()
    assert ctx["widget"]["bs_value"]  # has some BS string


def test_set_default_date_initial_uses_last_entry(monkeypatch):
    today = datetime.date(2024, 1, 2)
    last = datetime.date(2023, 12, 31)
    monkeypatch.setattr(timezone, "localdate", lambda: today)

    DummyModel = _stub_model(last_date=type("Obj", (), {"journal_date": last})(), has_org=True)

    class F(forms.Form):
        journal_date = forms.DateField()

        class Meta:
            model = DummyModel

    f = F()
    f.organization = object()
    set_default_date_initial(f, "journal_date", f.fields["journal_date"])
    assert f.fields["journal_date"].initial == last
    assert f.initial["journal_date"] == last


def test_set_default_date_initial_respects_today_seed(monkeypatch):
    today = datetime.date(2024, 1, 2)
    last = datetime.date(2023, 12, 31)
    monkeypatch.setattr(timezone, "localdate", lambda: today)

    DummyModel = _stub_model(last_date=type("Obj", (), {"journal_date": last})(), has_org=True)

    class OrgCfg:
        calendar_date_seed = DateSeedStrategy.TODAY

    class Org:
        config = OrgCfg()

    class F(forms.Form):
        journal_date = forms.DateField()

        class Meta:
            model = DummyModel

    f = F()
    f.organization = Org()
    set_default_date_initial(f, "journal_date", f.fields["journal_date"])
    assert f.fields["journal_date"].initial == today
    assert f.initial["journal_date"] == today
