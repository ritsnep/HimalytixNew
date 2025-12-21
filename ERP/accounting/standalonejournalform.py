"""
Standalone Journal Entry UI (Fallback)

- List / Create / Update (draft-only) journal entries.
- Reuses existing JournalForm + JournalLineFormSet.
- HTMX-friendly: returns partial templates for HX requests and triggers
  `standaloneJournal:saved` on successful create/update.

This version uses the project's accounting.mixins.PermissionRequiredMixin,
which also ensures an active organization context (important for org-scoped forms).
"""

import logging
from typing import Any, Dict

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpRequest
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView

from accounting.models import Journal
from accounting.forms.journal_form import JournalForm
from accounting.forms.journal_line_form import JournalLineFormSet
from accounting.mixins import PermissionRequiredMixin  # IMPORTANT: project mixin

logger = logging.getLogger(__name__)


def _is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true" or getattr(request, "htmx", False)


class StandaloneJournalForm(JournalForm):
    """Wrapper around JournalForm that hides `status` from the user."""

    class Meta(JournalForm.Meta):
        fields = [
            "journal_type",
            "period",
            "journal_date",
            "reference",
            "description",
            "currency_code",
            "exchange_rate",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("status", None)


StandaloneJournalLineFormSet = JournalLineFormSet


class StandaloneJournalListView(PermissionRequiredMixin, ListView):
    model = Journal
    template_name = "accounting/standalone_journal/journal_list.html"
    context_object_name = "journals"
    paginate_by = 25
    permission_required = ("accounting.view_voucher_entry",)

    def get_queryset(self):
        org = self.get_organization()
        return (
            Journal.objects.filter(organization=org)
            .select_related("journal_type", "period", "created_by", "posted_by")
            .order_by("-journal_date", "-journal_number")
        )


class StandaloneJournalCreateView(PermissionRequiredMixin, CreateView):
    model = Journal
    form_class = StandaloneJournalForm
    template_name = "accounting/standalone_journal/journal_form.html"
    permission_required = ("accounting.add_voucher_entry",)
    success_url = reverse_lazy("accounting:standalone_journal_list")

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.get_organization()
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        org = self.get_organization()

        if self.request.POST:
            context["line_formset"] = StandaloneJournalLineFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={"organization": org},
            )
        else:
            context["line_formset"] = StandaloneJournalLineFormSet(
                instance=self.object,
                form_kwargs={"organization": org},
            )

        context["form_action"] = self.request.path
        context["page_title"] = "New Journal Entry"
        context["submit_button_text"] = "Create"
        return context

    def form_valid(self, form: StandaloneJournalForm) -> HttpResponse:
        context = self.get_context_data()
        line_formset = context["line_formset"]
        org = self.get_organization()

        with transaction.atomic():
            form.instance.organization = org
            form.instance.created_by = self.request.user
            form.instance.status = "draft"
            self.object = form.save()

            if line_formset.is_valid():
                line_formset.instance = self.object
                lines = line_formset.save(commit=False)

                for line in lines:
                    if not getattr(line, "created_by_id", None):
                        line.created_by = self.request.user
                    line.save()

                for line in line_formset.deleted_objects:
                    line.delete()

                self.object.update_totals()
                self.object.save(update_fields=["total_debit", "total_credit"])

                alert_message = f"Journal {self.object.journal_number or self.object.id} created successfully."

                if _is_htmx(self.request):
                    context.update(
                        {
                            "alert_message": alert_message,
                            "alert_level": "success",
                            "form": StandaloneJournalForm(organization=org),
                            "line_formset": StandaloneJournalLineFormSet(
                                instance=Journal(),
                                form_kwargs={"organization": org},
                            ),
                        }
                    )
                    response = render(
                        self.request,
                        "accounting/standalone_journal/partials/journal_form.html",
                        context,
                    )
                    response["HX-Trigger"] = "standaloneJournal:saved"
                    return response

                messages.success(self.request, alert_message)
                return redirect(self.success_url)

            context["alert_message"] = "Please correct the errors in journal lines."
            context["alert_level"] = "danger"
            if _is_htmx(self.request):
                return render(
                    self.request,
                    "accounting/standalone_journal/partials/journal_form.html",
                    context,
                    status=422,
                )
            return render(self.request, self.template_name, context, status=422)

    def form_invalid(self, form: StandaloneJournalForm) -> HttpResponse:
        context = self.get_context_data(form=form)
        context["alert_message"] = "Please correct the errors below."
        context["alert_level"] = "danger"

        if _is_htmx(self.request):
            return render(
                self.request,
                "accounting/standalone_journal/partials/journal_form.html",
                context,
                status=422,
            )
        return render(self.request, self.template_name, context, status=422)


class StandaloneJournalUpdateView(PermissionRequiredMixin, UpdateView):
    model = Journal
    form_class = StandaloneJournalForm
    template_name = "accounting/standalone_journal/journal_form.html"
    permission_required = ("accounting.change_voucher_entry",)
    success_url = reverse_lazy("accounting:standalone_journal_list")

    def get_queryset(self):
        org = self.get_organization()
        return Journal.objects.filter(organization=org, status="draft")

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.get_organization()
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        org = self.get_organization()

        if self.request.POST:
            context["line_formset"] = StandaloneJournalLineFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={"organization": org},
            )
        else:
            context["line_formset"] = StandaloneJournalLineFormSet(
                instance=self.object,
                form_kwargs={"organization": org},
            )

        context["form_action"] = self.request.path
        context["page_title"] = f"Edit Journal {self.object.journal_number or self.object.id}"
        context["submit_button_text"] = "Update"
        return context

    def form_valid(self, form: StandaloneJournalForm) -> HttpResponse:
        context = self.get_context_data()
        line_formset = context["line_formset"]

        with transaction.atomic():
            form.instance.updated_by = self.request.user
            self.object = form.save()

            if line_formset.is_valid():
                line_formset.instance = self.object
                lines = line_formset.save(commit=False)

                for line in lines:
                    if not line.pk:
                        line.created_by = self.request.user
                    line.updated_by = self.request.user
                    line.save()

                for line in line_formset.deleted_objects:
                    line.delete()

                self.object.update_totals()
                self.object.save(update_fields=["total_debit", "total_credit"])

                alert_message = f"Journal {self.object.journal_number or self.object.id} updated successfully."

                if _is_htmx(self.request):
                    context.update({"alert_message": alert_message, "alert_level": "success"})
                    response = render(
                        self.request,
                        "accounting/standalone_journal/partials/journal_form.html",
                        context,
                    )
                    response["HX-Trigger"] = "standaloneJournal:saved"
                    return response

                messages.success(self.request, alert_message)
                return redirect(self.success_url)

            context["alert_message"] = "Please correct the errors in journal lines."
            context["alert_level"] = "danger"
            if _is_htmx(self.request):
                return render(
                    self.request,
                    "accounting/standalone_journal/partials/journal_form.html",
                    context,
                    status=422,
                )
            return render(self.request, self.template_name, context, status=422)

    def form_invalid(self, form: StandaloneJournalForm) -> HttpResponse:
        context = self.get_context_data(form=form)
        context["alert_message"] = "Please correct the errors below."
        context["alert_level"] = "danger"

        if _is_htmx(self.request):
            return render(
                self.request,
                "accounting/standalone_journal/partials/journal_form.html",
                context,
                status=422,
            )
        return render(self.request, self.template_name, context, status=422)
