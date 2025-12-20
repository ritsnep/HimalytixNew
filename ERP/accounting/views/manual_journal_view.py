"""
Manual Journal Entry View

This module provides a simple interface for creating manual journal entries
with inline journal lines. It uses the existing Journal and JournalLine models
and integrates with the PostingService for validation and posting.
"""

import logging
from decimal import Decimal
from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, UpdateView, ListView, DetailView

from accounting.forms.journal_form import JournalForm
from accounting.forms.journal_line_form import JournalLineFormSet
from accounting.models import Journal, JournalLine, AccountingPeriod
from accounting.services.posting_service import PostingService
from accounting.services.post_journal import post_journal, JournalPostingError, JournalValidationError
from usermanagement.mixins import UserOrganizationMixin

logger = logging.getLogger(__name__)


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true" or getattr(request, "htmx", False)


def _render_manual_journal_form(request, context, *, status=200):
    if _is_htmx(request):
        return render(
            request,
            "accounting/manual_journal/partials/journal_form.html",
            context,
            status=status,
        )
    return render(request, "accounting/manual_journal/journal_form.html", context, status=status)


class ManualJournalListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    """List view for manual journal entries."""
    
    model = Journal
    template_name = 'accounting/manual_journal/journal_list.html'
    context_object_name = 'journals'
    paginate_by = 25
    permission_required = ('accounting.view_voucher_entry',)
    
    def get_queryset(self):
        """Filter journals for current organization."""
        queryset = Journal.objects.filter(
            organization=self.organization
        ).select_related(
            'journal_type', 'period', 'created_by', 'posted_by'
        ).order_by('-journal_date', '-journal_number')
        
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(journal_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(journal_date__lte=end_date)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Journal.STATUS_CHOICES
        context['filters'] = {
            'status': self.request.GET.get('status', ''),
            'start_date': self.request.GET.get('start_date', ''),
            'end_date': self.request.GET.get('end_date', ''),
        }
        return context


class ManualJournalCreateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    """Create view for manual journal entries with inline lines."""
    
    model = Journal
    form_class = JournalForm
    template_name = 'accounting/manual_journal/journal_form.html'
    permission_required = ('accounting.add_voucher_entry',)
    success_url = reverse_lazy('accounting:manual_journal_list')
    
    def get_form_kwargs(self):
        """Pass organization to form."""
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.organization
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add formset to context."""
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['line_formset'] = JournalLineFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={'organization': self.organization}
            )
        else:
            context['line_formset'] = JournalLineFormSet(
                instance=self.object,
                form_kwargs={'organization': self.organization}
            )
        
        context['page_title'] = 'Create Manual Journal Entry'
        context['submit_button_text'] = 'Create Journal'
        context['form_action'] = self.request.path
        return context
    
    def form_valid(self, form):
        """Validate and save journal with lines."""
        context = self.get_context_data()
        line_formset = context['line_formset']
        
        with transaction.atomic():
            # Set organization and created_by
            form.instance.organization = self.organization
            form.instance.created_by = self.request.user
            form.instance.status = 'draft'
            
            # Save journal header
            self.object = form.save()

            # Validate and save lines
            if line_formset.is_valid():
                line_formset.instance = self.object
                lines = line_formset.save(commit=False)
                
                # Set created_by for each line
                for line in lines:
                    line.created_by = self.request.user
                    line.save()
                
                # Delete removed lines
                for line in line_formset.deleted_objects:
                    line.delete()
                
                # Update journal totals
                self.object.update_totals()
                self.object.save(update_fields=['total_debit', 'total_credit'])
                
                # Check if balanced
                if self.object.imbalance != Decimal('0'):
                    context["alert_message"] = (
                        f"Journal created but not balanced. Imbalance: {self.object.imbalance}"
                    )
                    context["alert_level"] = "warning"
                else:
                    context["alert_message"] = (
                        f"Journal {self.object.journal_number} created successfully."
                    )
                    context["alert_level"] = "success"

                if _is_htmx(self.request):
                    response = _render_manual_journal_form(self.request, context)
                    response["HX-Trigger"] = "manualJournal:saved"
                    return response

                messages.success(
                    self.request,
                    context.get("alert_message", "Journal saved."),
                )
                return redirect(self.success_url)
            else:
                context["alert_message"] = "Please correct the errors in journal lines."
                context["alert_level"] = "danger"
                return _render_manual_journal_form(self.request, context, status=422)
    
    def form_invalid(self, form):
        """Handle invalid form."""
        context = self.get_context_data(form=form)
        context["alert_message"] = "Please correct the errors below."
        context["alert_level"] = "danger"
        return _render_manual_journal_form(self.request, context, status=422)


class ManualJournalUpdateView(PermissionRequiredMixin, UserOrganizationMixin, UpdateView):
    """Update view for manual journal entries."""
    
    model = Journal
    form_class = JournalForm
    template_name = 'accounting/manual_journal/journal_form.html'
    permission_required = ('accounting.change_voucher_entry',)
    success_url = reverse_lazy('accounting:manual_journal_list')
    
    def get_queryset(self):
        """Filter to organization and only draft journals."""
        return Journal.objects.filter(
            organization=self.organization,
            status='draft'  # Only allow editing draft journals
        )
    
    def get_form_kwargs(self):
        """Pass organization to form."""
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = self.organization
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add formset to context."""
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['line_formset'] = JournalLineFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={'organization': self.organization}
            )
        else:
            context['line_formset'] = JournalLineFormSet(
                instance=self.object,
                form_kwargs={'organization': self.organization}
            )
        
        context['page_title'] = f'Edit Journal {self.object.journal_number}'
        context['submit_button_text'] = 'Update Journal'
        context['form_action'] = self.request.path
        return context
    
    def form_valid(self, form):
        """Validate and save journal with lines."""
        context = self.get_context_data()
        line_formset = context['line_formset']
        
        with transaction.atomic():
            # Set updated_by
            form.instance.updated_by = self.request.user
            
            # Save journal header
            self.object = form.save()
            
            # Validate and save lines
            if line_formset.is_valid():
                line_formset.instance = self.object
                lines = line_formset.save(commit=False)
                
                # Set updated_by for each line
                for line in lines:
                    if not line.pk:
                        line.created_by = self.request.user
                    line.updated_by = self.request.user
                    line.save()
                
                # Delete removed lines
                for line in line_formset.deleted_objects:
                    line.delete()
                
                # Update journal totals
                self.object.update_totals()
                self.object.save(update_fields=['total_debit', 'total_credit'])

                context["alert_message"] = (
                    f"Journal {self.object.journal_number} updated successfully."
                )
                context["alert_level"] = "success"

                if _is_htmx(self.request):
                    response = _render_manual_journal_form(self.request, context)
                    response["HX-Trigger"] = "manualJournal:updated"
                    return response

                messages.success(self.request, context["alert_message"])
                return redirect(self.success_url)
            else:
                context["alert_message"] = "Please correct the errors in journal lines."
                context["alert_level"] = "danger"
                return _render_manual_journal_form(self.request, context, status=422)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context["alert_message"] = "Please correct the errors below."
        context["alert_level"] = "danger"
        return _render_manual_journal_form(self.request, context, status=422)


class ManualJournalValidateView(PermissionRequiredMixin, UserOrganizationMixin, CreateView):
    """HTMX endpoint to validate manual journal without saving."""

    model = Journal
    form_class = JournalForm
    permission_required = ("accounting.add_voucher_entry",)

    def post(self, request, *args, **kwargs):
        form = JournalForm(request.POST or None, organization=self.organization)
        line_formset = JournalLineFormSet(
            request.POST or None,
            instance=None,
            form_kwargs={"organization": self.organization},
        )

        context = {
            "form": form,
            "line_formset": line_formset,
            "page_title": "Create Manual Journal Entry",
            "submit_button_text": "Create Journal",
            "form_action": request.path,
        }
        if form.is_valid() and line_formset.is_valid():
            context["alert_message"] = "Validation passed."
            context["alert_level"] = "success"
            return _render_manual_journal_form(request, context, status=200)

        context["alert_message"] = "Please correct the errors below."
        context["alert_level"] = "danger"
        return _render_manual_journal_form(request, context, status=422)


class ManualJournalDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """Detail view for manual journal entries."""
    
    model = Journal
    template_name = 'accounting/manual_journal/journal_detail.html'
    context_object_name = 'journal'
    permission_required = ('accounting.view_voucher_entry',)
    
    def get_queryset(self):
        """Filter to organization."""
        return Journal.objects.filter(
            organization=self.organization
        ).select_related(
            'journal_type', 'period', 'organization',
            'created_by', 'posted_by', 'approved_by'
        ).prefetch_related(
            'lines__account',
            'lines__department',
            'lines__project',
            'lines__cost_center'
        )
    
    def get_context_data(self, **kwargs):
        """Add journal lines and totals to context."""
        context = super().get_context_data(**kwargs)
        
        journal = self.object
        lines = journal.lines.all().order_by('line_number')
        
        context['lines'] = lines
        context['line_count'] = lines.count()
        context['is_balanced'] = journal.imbalance == Decimal('0')
        context['can_post'] = (
            journal.status == 'draft' and 
            context['is_balanced'] and
            self.request.user.has_perm('accounting.can_post_journal')
        )
        context['can_edit'] = (
            journal.status == 'draft' and
            self.request.user.has_perm('accounting.change_voucher_entry')
        )
        
        return context


class ManualJournalPostView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """Post a manual journal entry."""
    
    model = Journal
    permission_required = ('accounting.can_post_journal',)
    
    def get_queryset(self):
        """Filter to organization and draft journals."""
        return Journal.objects.filter(
            organization=self.organization,
            status='draft'
        )
    
    def post(self, request, *args, **kwargs):
        """Post the journal entry."""
        journal = self.get_object()
        
        try:
            # Use the posting service
            from accounting.utils.idempotency import resolve_idempotency_key
            posted_journal = post_journal(
                journal,
                user=request.user,
                idempotency_key=resolve_idempotency_key(request),
            )

            alert_message = f"Journal {posted_journal.journal_number} posted successfully."
            if _is_htmx(request):
                response = render(
                    request,
                    "accounting/manual_journal/partials/journal_alert.html",
                    {"alert_message": alert_message, "alert_level": "success"},
                )
                response["HX-Trigger"] = "manualJournal:posted"
                return response
            messages.success(request, alert_message)
            return redirect('accounting:manual_journal_detail', pk=posted_journal.pk)

        except (JournalValidationError, JournalPostingError) as e:
            # Format the message centrally and log
            try:
                from accounting.services.post_journal import format_journal_exception
                user_msg = format_journal_exception(e)
            except Exception:
                user_msg = str(e)
            if _is_htmx(request):
                return render(
                    request,
                    "accounting/manual_journal/partials/journal_alert.html",
                    {"alert_message": user_msg, "alert_level": "danger"},
                    status=422,
                )
            messages.error(request, user_msg)
            logger.error("Journal post failed: %s", user_msg, exc_info=True)

        except Exception as e:
            if _is_htmx(request):
                return render(
                    request,
                    "accounting/manual_journal/partials/journal_alert.html",
                    {"alert_message": f"Unexpected error: {str(e)}", "alert_level": "danger"},
                    status=500,
                )
            messages.error(request, f"Unexpected error: {str(e)}")
            logger.exception(f"Unexpected error posting journal: {e}")
        
        return redirect('accounting:manual_journal_detail', pk=journal.pk)
