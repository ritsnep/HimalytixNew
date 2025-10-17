"""
Voucher Edit View - Phase 2 Implementation

Handles editing of existing journal entries with:
- GET: Display journal with populated forms
- POST: Validate and update journal
- Protection: Prevent editing posted/approved journals
- Line management: Add, edit, delete lines
"""

import logging
from typing import Optional

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse

from accounting.forms.form_factory import VoucherFormFactory
from accounting.models import Journal
from accounting.services.validation import JournalValidationService
from accounting.views.base_voucher_view import BaseVoucherView, VoucherDetailMixin

logger = logging.getLogger(__name__)


class VoucherEditView(VoucherDetailMixin, BaseVoucherView):
    """
    View for editing existing journal entries.

    Handles:
    - GET: Display journal with populated forms
    - POST: Validate and update journal
    - Prevents editing of posted/approved journals
    - Line item management (add, edit, delete)
    - Organization context enforcement
    """

    template_name = 'accounting/journal_entry_form.html'
    page_title = 'Edit Journal Entry'
    model = Journal
    pk_url_kwarg = 'pk'

    def get_object(self) -> Optional[Journal]:
        """
        Get the journal instance to edit.

        Enforces:
        - Organization isolation
        - Journal exists
        - User has access

        Returns:
            Journal: The journal instance

        Raises:
            Http404: If journal not found or inaccessible
        """
        organization = self.get_organization()
        journal_id = self.kwargs.get(self.pk_url_kwarg)

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            logger.debug(
                f"Retrieved journal {journal.id} - "
                f"Status: {journal.status}, "
                f"Lines: {journal.lines.count()}"
            )

            return journal

        except Journal.DoesNotExist:
            logger.warning(
                f"Journal {journal_id} not found or not accessible "
                f"for org {organization.id}"
            )
            raise Http404("Journal not found")

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        Display journal entry form with existing data.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Rendered form template

        Raises:
            Http404: If journal not found
        """
        organization = self.get_organization()
        journal = self.get_object()

        # Check if journal can be edited
        if journal.status in ['posted', 'approved']:
            logger.warning(
                f"Edit attempt on {journal.status} journal {journal.id} "
                f"by user {request.user.username}"
            )
            messages.warning(
                request,
                f"Cannot edit a {journal.status} journal entry. "
                f"You can only view it."
            )
            return redirect(
                'accounting:journal_detail',
                pk=journal.id
            )

        # Create forms with existing data
        journal_form = VoucherFormFactory.get_journal_form(
            organization=organization,
            instance=journal
        )

        line_formset = VoucherFormFactory.get_journal_line_formset(
            organization=organization,
            instance=journal
        )

        context = self.get_context_data(
            object=journal,
            journal_form=journal_form,
            line_formset=line_formset,
            is_edit=True
        )

        logger.debug(
            f"VoucherEditView GET - Journal: {journal.id}, "
            f"User: {request.user.username}, "
            f"Lines: {line_formset.total_form_count()}"
        )

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Handle form submission for updating journal.

        Validates:
        1. Journal form
        2. Journal line formset
        3. Business rules
        4. Edit permission

        If valid:
        - Updates Journal instance
        - Updates JournalLine instances
        - Logs audit event
        - Redirects to detail view

        Args:
            request: HTTP request with POST data

        Returns:
            HttpResponse: Redirect or form with errors
        """
        organization = self.get_organization()
        journal = self.get_object()

        # Check if journal can be edited
        if journal.status in ['posted', 'approved']:
            logger.warning(
                f"Edit attempt on {journal.status} journal {journal.id}"
            )
            messages.error(
                request,
                f"Cannot edit a {journal.status} journal entry."
            )
            return redirect('accounting:journal_detail', pk=journal.id)

        # Bind forms with existing instance
        journal_form = VoucherFormFactory.get_journal_form(
            organization=organization,
            instance=journal,
            data=request.POST,
            files=request.FILES
        )

        line_formset = VoucherFormFactory.get_journal_line_formset(
            organization=organization,
            instance=journal,
            data=request.POST,
            files=request.FILES
        )

        # Validate forms
        is_valid, errors = VoucherFormFactory.validate_forms(
            journal_form,
            line_formset
        )

        if not is_valid:
            logger.warning(
                f"Validation failed for journal {journal.id} - "
                f"Journal errors: {journal_form.errors}, "
                f"Line errors: {[f.errors for f in line_formset.forms]}"
            )

            context = self.get_context_data(
                object=journal,
                journal_form=journal_form,
                line_formset=line_formset,
                is_edit=True,
                errors=errors
            )
            return self.render_to_response(context, status=400)

        # Perform business rule validation
        validation_service = JournalValidationService(organization)

        try:
            journal_data = journal_form.cleaned_data
            lines_data = [
                form.cleaned_data for form in line_formset.forms
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
            ]

            validation_errors = validation_service.validate_journal_entry(
                journal_data, lines_data
            )

            if validation_errors:
                logger.warning(
                    f"Business validation failed for journal {journal.id} - "
                    f"Errors: {validation_errors}"
                )

                context = self.get_context_data(
                    object=journal,
                    journal_form=journal_form,
                    line_formset=line_formset,
                    is_edit=True,
                    errors=validation_errors
                )
                return self.render_to_response(context, status=400)

            # Save changes
            self._save_journal_update(
                journal,
                journal_form,
                line_formset,
                request,
                organization
            )

            messages.success(
                request,
                f"Journal entry updated successfully. "
                f"Total Debit: {journal.total_debit}, "
                f"Total Credit: {journal.total_credit}"
            )

            logger.info(
                f"Journal {journal.id} updated by {request.user.username}"
            )

            return redirect(
                'accounting:journal_detail',
                pk=journal.id
            )

        except ValidationError as e:
            logger.error(f"Validation error updating journal: {e}")
            messages.error(request, f"Validation error: {str(e)}")

            context = self.get_context_data(
                object=journal,
                journal_form=journal_form,
                line_formset=line_formset,
                is_edit=True,
                errors={'validation': str(e)}
            )
            return self.render_to_response(context, status=400)

        except Exception as e:
            logger.exception(f"Unexpected error updating journal: {e}")
            messages.error(
                request,
                "An unexpected error occurred. Please try again."
            )

            context = self.get_context_data(
                object=journal,
                journal_form=journal_form,
                line_formset=line_formset,
                is_edit=True,
                errors={'general': 'An unexpected error occurred'}
            )
            return self.render_to_response(context, status=500)

    def _save_journal_update(
        self,
        journal: Journal,
        journal_form,
        line_formset,
        request,
        organization
    ) -> None:
        """
        Save journal and lines updates in a transaction.

        Args:
            journal: Journal instance to update
            journal_form: Bound and valid form
            line_formset: Bound and valid formset
            request: HTTP request (for user tracking)
            organization: Organization instance

        Raises:
            ValidationError: If save fails
        """
        try:
            with transaction.atomic():
                # Update journal
                journal = journal_form.save(commit=False)
                journal.updated_by = request.user
                journal.save()

                logger.debug(f"Journal {journal.id} updated")

                # Update lines
                line_formset.instance = journal
                line_formset.save()

                # Delete marked lines
                for form in line_formset.deleted_forms:
                    form.instance.delete()

                logger.debug(
                    f"Updated {len(line_formset.forms)} lines for journal {journal.id}"
                )

                # Log audit event
                self._log_audit_update(journal)

        except Exception as e:
            logger.exception(f"Error updating journal: {e}")
            raise ValidationError(f"Error updating journal: {str(e)}")

    def _log_audit_update(self, journal: Journal) -> None:
        """
        Log audit event for journal update.

        Args:
            journal: Journal instance
        """
        try:
            from django.contrib.contenttypes.models import ContentType
            from accounting.models import AuditLog

            content_type = ContentType.objects.get_for_model(Journal)
            AuditLog.objects.create(
                user=self.request.user,
                action='update',
                content_type=content_type,
                object_id=journal.id,
                changes={
                    'journal_type': str(journal.journal_type),
                    'total_debit': str(journal.total_debit),
                    'total_credit': str(journal.total_credit),
                    'status': journal.status
                },
                ip_address=self.get_client_ip()
            )

        except Exception as e:
            logger.warning(f"Failed to create audit log: {e}")
