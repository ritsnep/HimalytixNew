"""
Voucher Detail View - Phase 2 Implementation

Displays journal entries in read-only mode with:
- Journal header information
- All line items
- Audit trail
- Action buttons (edit, post, delete, duplicate, reverse)
- Organization context enforcement
"""

import logging
from typing import Optional, Dict, Any

from django.contrib import messages
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView

from accounting.models import Journal, AuditLog
from accounting.views.base_voucher_view import BaseVoucherView, VoucherDetailMixin

logger = logging.getLogger(__name__)


class VoucherDetailView(VoucherDetailMixin, BaseVoucherView, DetailView):
    """
    View for displaying journal entry details in read-only mode.

    Handles:
    - Display journal with all lines
    - Show audit trail
    - Action buttons for operations
    - Status-based button availability
    - Organization context enforcement
    """

    template_name = 'accounting/journal_entry_detail.html'
    model = Journal
    pk_url_kwarg = 'pk'
    page_title = 'Journal Entry Details'

    def get_object(self) -> Optional[Journal]:
        """
        Get the journal instance to display.

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
            journal = Journal.objects.select_related(
                'journal_type',
                'period',
                'organization',
                'currency',
                'created_by',
                'updated_by'
            ).prefetch_related('lines').get(
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

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """
        Build context with journal data and audit trail.

        Args:
            **kwargs: Additional context

        Returns:
            Dict[str, Any]: Context for template
        """
        context = super().get_context_data(**kwargs)
        journal = self.get_object()

        # Get audit trail
        audit_trail = self._get_audit_trail(journal)

        # Determine available actions
        actions = self._get_available_actions(journal)

        # Get line totals and status
        lines = journal.lines.all()
        line_count = lines.count()
        total_debit = sum(line.debit_amount or 0 for line in lines)
        total_credit = sum(line.credit_amount or 0 for line in lines)

        context.update({
            'journal': journal,
            'lines': lines,
            'line_count': line_count,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'is_balanced': total_debit == total_credit,
            'audit_trail': audit_trail,
            'available_actions': actions,
            'is_posted': journal.status == 'posted',
            'is_approved': journal.status == 'approved',
            'is_draft': journal.status == 'draft',
            'can_edit': journal.status in ['draft', 'pending'],
            'can_post': journal.status in ['draft', 'pending'],
            'can_delete': journal.status == 'draft',
            'can_duplicate': True,
            'can_reverse': journal.status in ['posted', 'approved']
        })

        logger.debug(
            f"VoucherDetailView context - Journal: {journal.id}, "
            f"Status: {journal.status}, "
            f"Lines: {line_count}, "
            f"Balance: {total_debit} = {total_credit}"
        )

        return context

    def _get_available_actions(self, journal: Journal) -> Dict[str, Dict[str, Any]]:
        """
        Determine which actions are available based on journal status.

        Args:
            journal: Journal instance

        Returns:
            Dict[str, Dict[str, Any]]: Actions with labels and confirmation
        """
        actions = {
            'edit': {
                'label': 'Edit',
                'url': reverse(
                    'accounting:journal_edit',
                    kwargs={'pk': journal.id}
                ),
                'available': journal.status in ['draft', 'pending'],
                'css_class': 'btn-warning',
                'icon': 'pencil',
                'confirm': False
            },
            'post': {
                'label': 'Post',
                'url': reverse(
                    'accounting:journal_post',
                    kwargs={'pk': journal.id}
                ),
                'available': journal.status in ['draft', 'pending'],
                'css_class': 'btn-success',
                'icon': 'check-circle',
                'confirm': True,
                'confirm_message': 'Post this journal entry? '
                                  'This action cannot be undone.'
            },
            'delete': {
                'label': 'Delete',
                'url': reverse(
                    'accounting:journal_delete',
                    kwargs={'pk': journal.id}
                ),
                'available': journal.status == 'draft',
                'css_class': 'btn-danger',
                'icon': 'trash',
                'confirm': True,
                'confirm_message': 'Delete this journal entry? '
                                  'This action cannot be undone.'
            },
            'duplicate': {
                'label': 'Duplicate',
                'url': reverse(
                    'accounting:journal_duplicate',
                    kwargs={'pk': journal.id}
                ),
                'available': True,
                'css_class': 'btn-info',
                'icon': 'copy',
                'confirm': False
            },
            'reverse': {
                'label': 'Reverse',
                'url': reverse(
                    'accounting:journal_reverse',
                    kwargs={'pk': journal.id}
                ),
                'available': journal.status in ['posted', 'approved'],
                'css_class': 'btn-secondary',
                'icon': 'arrow-counterclockwise',
                'confirm': True,
                'confirm_message': 'Reverse this journal entry? '
                                  'A new entry will be created with opposite amounts.'
            }
        }

        logger.debug(
            f"Available actions for journal {journal.id}: "
            f"{[k for k, v in actions.items() if v['available']]}"
        )

        return actions

    def _get_audit_trail(self, journal: Journal) -> list:
        """
        Get audit trail for the journal.

        Args:
            journal: Journal instance

        Returns:
            list: Audit log entries ordered by creation date
        """
        try:
            from django.contrib.contenttypes.models import ContentType

            content_type = ContentType.objects.get_for_model(Journal)
            audit_logs = AuditLog.objects.filter(
                content_type=content_type,
                object_id=journal.id
            ).select_related('user').order_by('-created_at')

            audit_trail = []
            for log in audit_logs:
                audit_trail.append({
                    'user': log.user.get_full_name() or log.user.username,
                    'action': log.get_action_display(),
                    'timestamp': log.created_at,
                    'changes': log.changes,
                    'ip_address': log.ip_address
                })

            logger.debug(
                f"Retrieved {len(audit_trail)} audit entries for journal {journal.id}"
            )

            return audit_trail

        except Exception as e:
            logger.warning(f"Failed to retrieve audit trail: {e}")
            return []


class VoucherDetailActionView(BaseVoucherView):
    """
    Base class for detail page action views (post, delete, duplicate, reverse).

    Provides common functionality for status-based operations.
    """

    model = Journal
    pk_url_kwarg = 'pk'

    def get_object(self) -> Optional[Journal]:
        """
        Get the journal instance.

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
            return journal

        except Journal.DoesNotExist:
            raise Http404("Journal not found")

    def _check_permission(self, journal: Journal, action: str) -> bool:
        """
        Check if action is permitted on journal.

        Args:
            journal: Journal instance
            action: Action name ('post', 'delete', 'reverse', etc.)

        Returns:
            bool: True if action is permitted
        """
        permissions = {
            'post': ['draft', 'pending'],
            'delete': ['draft'],
            'reverse': ['posted', 'approved']
        }

        allowed_statuses = permissions.get(action, [])
        is_permitted = journal.status in allowed_statuses

        if not is_permitted:
            logger.warning(
                f"Action '{action}' not permitted on {journal.status} journal {journal.id}"
            )

        return is_permitted


class VoucherPostView(VoucherDetailActionView):
    """View for posting journal entries."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Post a journal entry (change status to posted).

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Redirect to detail view
        """
        journal = self.get_object()

        if not self._check_permission(journal, 'post'):
            messages.error(
                request,
                f"Cannot post a {journal.status} journal entry."
            )
            return redirect('accounting:journal_detail', pk=journal.id)

        try:
            journal.status = 'posted'
            journal.posted_by = request.user
            journal.save()

            logger.info(f"Journal {journal.id} posted by {request.user.username}")
            messages.success(request, "Journal entry posted successfully.")

        except Exception as e:
            logger.exception(f"Error posting journal: {e}")
            messages.error(request, "Error posting journal entry.")

        return redirect('accounting:journal_detail', pk=journal.id)


class VoucherDeleteView(VoucherDetailActionView):
    """View for deleting journal entries."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Delete a journal entry.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Redirect to list view
        """
        journal = self.get_object()

        if not self._check_permission(journal, 'delete'):
            messages.error(
                request,
                f"Cannot delete a {journal.status} journal entry."
            )
            return redirect('accounting:journal_detail', pk=journal.id)

        try:
            journal_id = journal.id
            journal.delete()

            logger.info(f"Journal {journal_id} deleted by {request.user.username}")
            messages.success(request, "Journal entry deleted successfully.")

        except Exception as e:
            logger.exception(f"Error deleting journal: {e}")
            messages.error(request, "Error deleting journal entry.")

        return redirect('accounting:journal_list')


class VoucherDuplicateView(VoucherDetailActionView):
    """View for duplicating journal entries."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Duplicate a journal entry.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Redirect to new journal edit view
        """
        from django.db import transaction
        from accounting.forms.form_factory import VoucherFormFactory

        journal = self.get_object()
        organization = self.get_organization()

        try:
            with transaction.atomic():
                # Create new journal with same data
                new_journal = Journal(
                    organization=journal.organization,
                    journal_type=journal.journal_type,
                    period=journal.period,
                    currency=journal.currency,
                    notes=f"Duplicate of {journal.reference_no}: {journal.notes}",
                    reference_no=None,  # Clear reference for new entry
                    status='draft'
                )
                new_journal.save()

                # Copy all lines
                for line in journal.lines.all():
                    from accounting.models import JournalLine
                    JournalLine.objects.create(
                        journal=new_journal,
                        account=line.account,
                        debit_amount=line.debit_amount,
                        credit_amount=line.credit_amount,
                        description=line.description,
                        department=line.department,
                        project=line.project,
                        cost_center=line.cost_center,
                        tax_code=line.tax_code,
                        tax_amount=line.tax_amount,
                        currency=line.currency,
                        exchange_rate=line.exchange_rate
                    )

                logger.info(
                    f"Journal {journal.id} duplicated to {new_journal.id} "
                    f"by {request.user.username}"
                )
                messages.success(
                    request,
                    f"Journal entry duplicated successfully. "
                    f"New reference: {new_journal.reference_no}"
                )

                return redirect(
                    'accounting:journal_edit',
                    pk=new_journal.id
                )

        except Exception as e:
            logger.exception(f"Error duplicating journal: {e}")
            messages.error(request, "Error duplicating journal entry.")
            return redirect('accounting:journal_detail', pk=journal.id)


class VoucherReverseView(VoucherDetailActionView):
    """View for reversing journal entries."""

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Reverse a journal entry (create reverse entry).

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Redirect to new journal detail view
        """
        from django.db import transaction
        from accounting.models import Journal, JournalLine

        journal = self.get_object()
        organization = self.get_organization()

        if not self._check_permission(journal, 'reverse'):
            messages.error(
                request,
                f"Cannot reverse a {journal.status} journal entry."
            )
            return redirect('accounting:journal_detail', pk=journal.id)

        try:
            with transaction.atomic():
                # Create reverse journal
                reverse_journal = Journal(
                    organization=journal.organization,
                    journal_type=journal.journal_type,
                    period=journal.period,
                    currency=journal.currency,
                    notes=f"Reverse of {journal.reference_no}: {journal.notes}",
                    reference_no=None,
                    status='posted'  # Auto-post reversed entries
                )
                reverse_journal.save()

                # Create reverse lines (swap debit/credit)
                for line in journal.lines.all():
                    JournalLine.objects.create(
                        journal=reverse_journal,
                        account=line.account,
                        debit_amount=line.credit_amount,  # Swap
                        credit_amount=line.debit_amount,  # Swap
                        description=f"Reversal: {line.description}",
                        department=line.department,
                        project=line.project,
                        cost_center=line.cost_center,
                        tax_code=line.tax_code,
                        tax_amount=-(line.tax_amount or 0),  # Negate
                        currency=line.currency,
                        exchange_rate=line.exchange_rate
                    )

                logger.info(
                    f"Journal {journal.id} reversed to {reverse_journal.id} "
                    f"by {request.user.username}"
                )
                messages.success(
                    request,
                    f"Journal entry reversed successfully. "
                    f"Reverse reference: {reverse_journal.reference_no}"
                )

                return redirect(
                    'accounting:journal_detail',
                    pk=reverse_journal.id
                )

        except Exception as e:
            logger.exception(f"Error reversing journal: {e}")
            messages.error(request, "Error reversing journal entry.")
            return redirect('accounting:journal_detail', pk=journal.id)
