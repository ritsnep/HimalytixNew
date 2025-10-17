"""
Voucher Create View - Phase 2 Implementation

Handles creation of new journal entries with:
- GET: Display empty forms
- POST: Validate and save journal with lines
- HTMX support for adding lines dynamically
"""

import logging
from decimal import Decimal
from typing import Dict, Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounting.forms.form_factory import VoucherFormFactory
from accounting.models import Journal, JournalLine
from accounting.services.validation import JournalValidationService
from accounting.views.base_voucher_view import BaseVoucherView

logger = logging.getLogger(__name__)


class VoucherCreateView(BaseVoucherView):
    """
    View for creating new journal entries.

    Handles:
    - GET: Display empty journal entry form
    - POST: Validate and save journal entry
    - Organization context enforcement
    - Transaction management
    - Audit logging
    """

    template_name = 'accounting/journal_entry_form.html'
    htmx_template_name = 'accounting/partials/journal_line_form.html'
    page_title = 'Create New Journal Entry'

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        Display empty journal entry form.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Rendered form template
        """
        organization = self.get_organization()
        journal_type = self.get_journal_type()

        # Create empty forms
        journal_form = VoucherFormFactory.get_journal_form(
            organization=organization,
            journal_type=journal_type
        )

        line_formset = VoucherFormFactory.get_journal_line_formset(
            organization=organization
        )

        context = self.get_context_data(
            journal_form=journal_form,
            line_formset=line_formset,
            is_create=True
        )

        logger.debug(
            f"VoucherCreateView GET - User: {request.user.username}, "
            f"Org: {organization.id}, Type: {journal_type}"
        )

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Handle form submission for creating new journal.

        Validates:
        1. Journal form
        2. Journal line formset
        3. Business rules (balance, dates, etc.)

        If valid:
        - Creates Journal instance
        - Creates JournalLine instances
        - Logs audit event
        - Redirects to detail view

        If invalid:
        - Returns form with errors

        Args:
            request: HTTP request with POST data

        Returns:
            HttpResponse: Redirect or form with errors
        """
        organization = self.get_organization()

        # Bind forms with POST data
        journal_form = VoucherFormFactory.get_journal_form(
            organization=organization,
            data=request.POST,
            files=request.FILES
        )

        line_formset = VoucherFormFactory.get_journal_line_formset(
            organization=organization,
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
                f"Form validation failed - User: {request.user.username}, "
                f"Journal errors: {journal_form.errors}, "
                f"Line errors: {[f.errors for f in line_formset.forms]}"
            )

            context = self.get_context_data(
                journal_form=journal_form,
                line_formset=line_formset,
                is_create=True,
                errors=errors
            )
            return self.render_to_response(context, status=400)

        # Perform business rule validation
        validation_service = JournalValidationService(organization)

        try:
            # Prepare data for validation service
            journal_data = journal_form.cleaned_data
            lines_data = [
                form.cleaned_data for form in line_formset.forms
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
            ]

            # Validate business rules
            validation_errors = validation_service.validate_journal_entry(
                journal_data, lines_data
            )

            if validation_errors:
                logger.warning(
                    f"Business validation failed - User: {request.user.username}, "
                    f"Errors: {validation_errors}"
                )

                context = self.get_context_data(
                    journal_form=journal_form,
                    line_formset=line_formset,
                    is_create=True,
                    errors=validation_errors
                )
                return self.render_to_response(context, status=400)

            # Save journal and lines
            journal = self._save_journal(
                journal_form,
                line_formset,
                request,
                organization
            )

            # Determine action (save draft vs post)
            action = request.POST.get('action', 'save')

            if action == 'post':
                # Post the journal
                journal.post()
                logger.info(
                    f"Journal {journal.id} posted - User: {request.user.username}"
                )
                messages.success(
                    request,
                    f"Journal entry created and posted successfully. "
                    f"Total Debit: {journal.total_debit}, "
                    f"Total Credit: {journal.total_credit}"
                )
            else:
                logger.info(
                    f"Journal {journal.id} saved as draft - User: {request.user.username}"
                )
                messages.success(
                    request,
                    f"Journal entry saved as draft. "
                    f"Total Debit: {journal.total_debit}, "
                    f"Total Credit: {journal.total_credit}"
                )

            # Redirect to detail view
            return redirect(
                'accounting:journal_detail',
                pk=journal.id
            )

        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            messages.error(request, f"Validation error: {str(e)}")

            context = self.get_context_data(
                journal_form=journal_form,
                line_formset=line_formset,
                is_create=True,
                errors={'validation': str(e)}
            )
            return self.render_to_response(context, status=400)

        except Exception as e:
            logger.exception(f"Unexpected error creating journal: {e}")
            messages.error(
                request,
                "An unexpected error occurred. Please try again."
            )

            context = self.get_context_data(
                journal_form=journal_form,
                line_formset=line_formset,
                is_create=True,
                errors={'general': 'An unexpected error occurred'}
            )
            return self.render_to_response(context, status=500)

    def _save_journal(
        self,
        journal_form,
        line_formset,
        request,
        organization
    ) -> Journal:
        """
        Save journal and related lines in a transaction.

        Args:
            journal_form: Bound and valid JournalForm
            line_formset: Bound and valid JournalLineFormSet
            request: HTTP request (for user tracking)
            organization: Organization instance

        Returns:
            Journal: Saved journal instance

        Raises:
            ValidationError: If save fails
        """
        try:
            with transaction.atomic():
                # Save journal
                journal = journal_form.save(commit=False)
                journal.organization = organization
                journal.created_by = request.user
                journal.save()

                logger.debug(f"Journal {journal.id} created")

                # Save lines
                line_formset.instance = journal
                line_formset.save()

                logger.debug(
                    f"Saved {len(line_formset.forms)} lines for journal {journal.id}"
                )

                # Log audit event
                self._log_audit(journal, 'create')

                return journal

        except Exception as e:
            logger.exception(f"Error saving journal: {e}")
            raise ValidationError(f"Error saving journal: {str(e)}")

    def _log_audit(self, journal: Journal, action: str) -> None:
        """
        Log audit event for the journal.

        Args:
            journal: Journal instance
            action: Action performed
        """
        try:
            from django.contrib.contenttypes.models import ContentType
            from accounting.models import AuditLog

            content_type = ContentType.objects.get_for_model(Journal)
            AuditLog.objects.create(
                user=self.request.user,
                action=action,
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
            logger.debug(f"Audit log created for journal {journal.id}")

        except Exception as e:
            logger.warning(f"Failed to create audit log: {e}")


class VoucherCreateHtmxView(BaseVoucherView):
    """
    HTMX handler for adding new blank journal lines.

    Returns HTML fragment for a new line form.
    """

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        Return HTML fragment for a new blank line.

        Args:
            request: HTTP request with form_count in GET params

        Returns:
            HttpResponse: HTML fragment with blank line form
        """
        organization = self.get_organization()

        # Get form count from request
        form_count = request.GET.get('form_count', '0')
        try:
            form_count = int(form_count)
        except (ValueError, TypeError):
            form_count = 0

        logger.debug(
            f"Creating blank line form - form_count: {form_count}, "
            f"Org: {organization.id}"
        )

        # Create blank line form
        blank_line = VoucherFormFactory.create_blank_line_form(
            organization=organization,
            form_index=form_count
        )

        context = {
            'form': blank_line,
            'form_index': form_count,
            'organization': organization,
        }

        return self.render_to_response(
            context,
            template_name='accounting/partials/journal_line_form.html'
        )


class VoucherAccountLookupHtmxView(BaseVoucherView):
    """
    HTMX handler for account lookup with search.

    Returns matching accounts as options.
    """

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        Return account options matching search query.

        Query parameters:
        - search: Search text (code or name)
        - account_type: Filter by account type

        Returns:
            HttpResponse: HTML with account options
        """
        from accounting.models import ChartOfAccount

        organization = self.get_organization()
        search = request.GET.get('search', '').strip()
        account_type = request.GET.get('account_type', '').strip()

        # Build query
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            is_active=True
        )

        if search:
            from django.db.models import Q
            accounts = accounts.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )

        if account_type:
            accounts = accounts.filter(account_type__code=account_type)

        # Limit results
        accounts = accounts[:20]

        logger.debug(
            f"Account lookup - search: '{search}', "
            f"type: {account_type}, results: {accounts.count()}"
        )

        context = {
            'accounts': accounts,
            'search': search,
        }

        return self.render_to_response(
            context,
            template_name='accounting/partials/account_options.html'
        )


class VoucherTaxCalculationHtmxView(BaseVoucherView):
    """
    HTMX handler for tax calculation.

    Returns calculated tax amount based on amount and tax rate.
    """

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        Calculate and return tax amount.

        Query parameters:
        - amount: Base amount for tax calculation
        - tax_rate: Tax rate percentage
        - line_index: Line form index

        Returns:
            HttpResponse: JSON with calculated tax
        """
        try:
            amount = Decimal(request.GET.get('amount', '0'))
            tax_rate = Decimal(request.GET.get('tax_rate', '0'))
            line_index = request.GET.get('line_index', '0')

            # Calculate tax
            if amount > 0 and tax_rate > 0:
                tax_amount = (amount * tax_rate) / Decimal('100')
            else:
                tax_amount = Decimal('0')

            logger.debug(
                f"Tax calculation - amount: {amount}, "
                f"rate: {tax_rate}, tax: {tax_amount}"
            )

            return self.json_response({
                'success': True,
                'tax_amount': str(tax_amount.quantize(Decimal('0.01'))),
                'line_index': line_index
            })

        except Exception as e:
            logger.error(f"Tax calculation error: {e}")
            return self.json_response({
                'success': False,
                'error': str(e)
            }, status=400)
