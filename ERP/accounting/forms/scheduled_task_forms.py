from django import forms

from accounting.forms_mixin import BootstrapFormMixin
from accounting.models import ScheduledReport


class AccountingPeriodCloseForm(forms.Form):
    """Simple confirmation form for period close."""

    confirm = forms.BooleanField(
        required=True,
        initial=True,
        label="Confirm close",
        help_text="Closing will lock the period and post closing entries.",
    )


class ScheduledReportForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ScheduledReport
        fields = [
            "organization",
            "name",
            "description",
            "report_type",
            "frequency",
            "format",
            "day_of_week",
            "day_of_month",
            "time_of_day",
            "recipients",
            "parameters",
            "is_active",
            "next_run_date",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "recipients": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "parameters": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "time_of_day": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        }
