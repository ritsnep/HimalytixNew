import datetime
from typing import Any, Optional

from django import forms
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date

from utils.calendars import (
    CalendarMode,
    DateSeedStrategy,
    ad_to_bs_string,
    bs_to_ad_string,
    maybe_coerce_bs_date,
    get_calendar_mode,
)


def set_default_date_initial(form: forms.BaseForm, name: str, field: forms.Field) -> None:
    """
    Set a sensible initial for DateFields: latest existing record (scoped to org when available), else today.
    Skip when data is bound or an explicit initial/instance value is present.
    """
    if getattr(form, "data", None):
        return
    if field.initial or (hasattr(form, "initial") and form.initial.get(name)):
        return
    instance_val = getattr(getattr(form, "instance", None), name, None)
    if instance_val:
        return

    today = timezone.localdate() if hasattr(timezone, "localdate") else datetime.date.today()
    chosen = today

    # Respect org config for seeding strategy
    org = getattr(form, "organization", None)
    seed_strategy = DateSeedStrategy.DEFAULT
    if org:
        cfg = getattr(org, "config", None)
        seed_strategy = DateSeedStrategy.normalize(getattr(cfg, "calendar_date_seed", None))

    model = getattr(getattr(form, "Meta", None), "model", None)
    if model:
        try:
            model_field = model._meta.get_field(name)
        except Exception:
            model_field = None
        if model_field and isinstance(model_field, (models.DateField, models.DateTimeField)):
            qs = model.objects.all()
            if org and any(f.name == "organization" for f in model._meta.fields):
                qs = qs.filter(organization=org)
            if seed_strategy != DateSeedStrategy.TODAY:
                try:
                    last_obj = qs.exclude(**{name: None}).order_by(f"-{name}").only(name).first()
                    if last_obj:
                        val = getattr(last_obj, name, None)
                        if isinstance(val, datetime.datetime):
                            val = val.date()
                        if val:
                            chosen = val
                except Exception:
                    pass
    field.initial = chosen
    # Ensure form.initial mirrors the field default so widgets receive it.
    if not getattr(form, "initial", None):
        form.initial = {}
    form.initial.setdefault(name, chosen)


def dual_date_widget(attrs=None, organization=None, default_view=None):
    """Factory for a DualCalendarWidget with org-aware default view."""
    view = get_calendar_mode(organization, default=default_view or CalendarMode.DUAL)
    return DualCalendarWidget(default_view=view, attrs=attrs or {})


class DualCalendarWidget(forms.Widget):
    """
    Dual (AD/BS) calendar widget that always submits an AD date string.

    Renders paired AD/BS inputs plus a toggle button. The AD input keeps the
    actual field name so Django receives a Gregorian date even if BS is shown.
    """

    template_name = "widgets/dual_calendar_widget.html"

    def __init__(self, default_view: str = CalendarMode.DEFAULT, attrs: Optional[dict[str, Any]] = None):
        self.default_view = CalendarMode.normalize(default_view)
        super().__init__(attrs)

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime.datetime):
            return value.date().isoformat()
        if isinstance(value, datetime.date):
            return value.isoformat()
        if isinstance(value, str):
            parsed = parse_date(value.strip())
            return parsed.isoformat() if parsed else value
        return str(value)

    def get_context(self, name: str, value: Any, attrs: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        attrs = attrs or {}
        context = super().get_context(name, value, attrs)

        ad_value = self._format_value(value)
        if not ad_value:
            # Final fallback to today to avoid empty renders in create forms.
            today = timezone.localdate() if hasattr(timezone, "localdate") else datetime.date.today()
            ad_value = today.isoformat()
        bs_value = ad_to_bs_string(ad_value) if ad_value else ""
        ad_input_id = attrs.get("id", f"id_{name}")
        bs_input_id = f"{ad_input_id}_bs"
        initial_view = (attrs.pop("data-initial-view", None) or "").upper()
        mode = CalendarMode.normalize(self.default_view)
        start_view = (
            initial_view
            if initial_view in {"AD", "BS"}
            else ("BS" if mode == CalendarMode.DUAL else mode)
        )

        # Build separate attrs for BS input (keep core classes).
        base_classes = (attrs.get("class", "") or "").strip()
        if "form-control" not in base_classes.split():
            base_classes = f"{base_classes} form-control".strip()
        bs_classes = f"{base_classes} dual-calendar__bs".strip()
        ad_classes = f"{base_classes} dual-calendar__ad".strip()

        context["widget"].update(
            {
                "name": name,
                "ad_value": ad_value,
                "bs_value": bs_value or "",
                "ad_input_id": ad_input_id,
                "bs_input_id": bs_input_id,
                "mode": mode,
                "start_view": start_view,
                "bs_name": f"{name}_bs",
                "ad_class": ad_classes,
                "bs_class": bs_classes,
            }
        )
        # Preserve attrs on the AD input only; BS input is built separately.
        context["widget"]["attrs"]["class"] = ad_classes
        context["widget"]["attrs"].setdefault("type", "date")
        return context

    def value_from_datadict(self, data, files, name):
        # Prefer explicitly submitted AD value.
        ad_value = data.get(name) or data.get(f"{name}_ad")
        if ad_value:
            return ad_value

        # Fall back to BS if JS failed and the BS field was submitted.
        bs_value = data.get(f"{name}_bs") or data.get(f"{name}-bs")
        if bs_value:
            converted = bs_to_ad_string(bs_value) or maybe_coerce_bs_date(bs_value)
            if converted:
                return converted if isinstance(converted, str) else converted.isoformat()
            return bs_value
        return None

    class Media:
        css = {"all": ["libs/nepali-datepicker/css/nepali.datepicker.v5.0.6.min.css"]}
        js = [
            "libs/nepali-datepicker/js/nepali.datepicker.v5.0.6.min.js",
            "js/dual-calendar.js",
        ]
