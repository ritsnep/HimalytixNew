from django import forms
from accounting.models import AccountingPeriod, FiscalYear
from accounting.forms_mixin import BootstrapFormMixin


class AccountingPeriodForm(BootstrapFormMixin, forms.ModelForm):
    """Form for creating and updating accounting periods.

    The fiscal year choices are limited to the user's organization to prevent
    cross-organization data leaks.  Basic widgets are added for consistent
    styling via :class:`BootstrapFormMixin`.
    """

    fiscal_year = forms.ModelChoiceField(
        queryset=FiscalYear.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=True,
        label="Fiscal Year",
    )

    class Meta:
        model = AccountingPeriod
        fields = (
            "fiscal_year",
            "name",
            "period_number",
            "start_date",
            "end_date",
            "status",
            "is_current",
            "is_adjustment_period",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "period_number": forms.NumberInput(attrs={"class": "form-control"}),
            "start_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "end_date": forms.TextInput(attrs={"class": "form-control datepicker"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_current": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_adjustment_period": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization:
            self.fields["fiscal_year"].queryset = FiscalYear.objects.filter(
                organization=self.organization
            )
        else:
            self.fields["fiscal_year"].queryset = FiscalYear.objects.none()