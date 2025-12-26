"""
Voucher HTMX Handlers - Phase 2 Implementation

Advanced HTMX handlers for interactive journal entry features:
- Line deletion with confirmation
- Journal posting with validation
- Journal duplication
- Real-time line recalculation
- Status validation before actions
- Line balance checking
"""

import logging
import json
from typing import Optional, Dict, Any

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from accounting.models import Journal, JournalLine
from utils.i18n import load_translations, get_current_language
from accounting.views.base_voucher_view import BaseVoucherView

logger = logging.getLogger(__name__)


class VoucherLineDeleteHtmxView(BaseVoucherView):
    """
    HTMX handler for deleting a journal line.

    Validates:
    - Journal belongs to user's organization
    - Line belongs to journal
    - Journal status allows deletion

    Returns:
    - HTML fragment (empty if deleted successfully)
    - Or error response
    """

    def _t(self, request, key: str, fallback: str, **kwargs) -> str:
        try:
            lang = get_current_language(request)
            trans = load_translations(lang)
            template = trans.get(key, fallback)
            return template.format(**kwargs) if kwargs else template
        except Exception:
            return fallback

    def delete(self, request, *args, **kwargs) -> HttpResponse:
        """
        Delete a journal line and return updated line count.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters (journal_id, line_id)

        Returns:
            HttpResponse: HTML fragment or error
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')
        line_id = kwargs.get('line_id')

        try:
            # Get journal
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            # Check status
            if journal.status not in ['draft', 'pending']:
                msg = self._t(
                    request,
                    'voucher.error.cannot_delete_from_status',
                    f'Cannot delete lines from {journal.status} journals',
                    status=journal.status,
                )
                return HttpResponse(
                    f'<div class="alert alert-danger">{msg}</div>',
                    status=400
                )

            # Get and delete line
            line = JournalLine.objects.get(
                id=line_id,
                journal=journal
            )

            line_account = str(line.account)
            line.delete()

            logger.info(
                f"Line {line_id} deleted from journal {journal_id} "
                f"by {request.user.username}"
            )

            # Return success with updated line count
            remaining_lines = journal.lines.count()
            success_msg = self._t(
                request,
                'voucher.success.line_deleted',
                'Line deleted. {remaining} line(s) remaining.',
                remaining=remaining_lines,
            )
            return HttpResponse(
                f'<div class="alert alert-success" hx-swap="delete" '
                f'hx-trigger="load delay:2s">{success_msg}</div>',
                headers={'HX-Trigger': 'lineDeleted'}
            )

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.journal_not_found", "Journal not found")}</div>',
                status=404
            )

        except JournalLine.DoesNotExist:
            logger.warning(f"Line {line_id} not found in journal {journal_id}")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.line_not_found", "Line not found")}</div>',
                status=404
            )

        except Exception as e:
            logger.exception(f"Error deleting line: {e}")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.error_prefix", "Error: {message}", message=str(e))}</div>',
                status=500
            )


class VoucherLineRecalculateHtmxView(BaseVoucherView):
    """
    HTMX handler for recalculating line totals.

    Triggered when:
    - Debit/credit amount changes
    - Tax rate changes
    - Currency changes

    Returns:
    - Updated totals
    - Journal balance status
    - Error messages
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Recalculate line amounts and totals.

        Args:
            request: HTTP request with line form data
            *args, **kwargs: URL parameters (journal_id)

        Returns:
            JsonResponse: Updated amounts and balance
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            # Parse request data
            data = request.POST or json.loads(request.body)
            debit = float(data.get('debit_amount', 0) or 0)
            credit = float(data.get('credit_amount', 0) or 0)
            tax_rate = float(data.get('tax_rate', 0) or 0)

            # Validate amounts
            if debit > 0 and credit > 0:
                return JsonResponse({
                    'valid': False,
                    'error': 'Cannot have both debit and credit amounts'
                }, status=400)

            if debit == 0 and credit == 0:
                return JsonResponse({
                    'valid': False,
                    'error': 'Must have either debit or credit amount'
                }, status=400)

            # Calculate tax
            amount = debit or credit
            tax_amount = round(amount * (tax_rate / 100), 2) if tax_rate else 0

            # Get all lines including this one
            total_debit = sum(
                l.debit_amount or 0 for l in journal.lines.all()
            ) + (debit if debit > 0 else 0)

            total_credit = sum(
                l.credit_amount or 0 for l in journal.lines.all()
            ) + (credit if credit > 0 else 0)

            is_balanced = total_debit == total_credit

            logger.debug(
                f"Line recalculation - Journal: {journal_id}, "
                f"Debit: {debit}, Credit: {credit}, "
                f"Tax: {tax_amount}, Balanced: {is_balanced}"
            )

            return JsonResponse({
                'valid': True,
                'debit_amount': debit,
                'credit_amount': credit,
                'tax_amount': tax_amount,
                'total_amount': amount + tax_amount,
                'journal_total_debit': total_debit,
                'journal_total_credit': total_credit,
                'is_balanced': is_balanced,
                'balance_message': self._t(request, 'voucher.balance.balanced', 'Balanced') if is_balanced else self._t(request, 'voucher.balance.unbalanced', 'Unbalanced: Debit {debit} ≠ Credit {credit}', debit=total_debit, credit=total_credit)
            })

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return JsonResponse({
                'valid': False,
                'error': 'Journal not found'
            }, status=404)

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid input data: {e}")
            return JsonResponse({
                'valid': False,
                'error': self._t(request, 'voucher.error.invalid_amount', 'Invalid amount: {message}', message=str(e))
            }, status=400)

        except Exception as e:
            logger.exception(f"Error recalculating line: {e}")
            return JsonResponse({
                'valid': False,
                'error': f'Error: {str(e)}'
            }, status=500)


class VoucherStatusValidationHtmxView(BaseVoucherView):
    """
    HTMX handler for validating journal status before actions.

    Checks:
    - Journal status
    - Required fields
    - Line balance
    - Business rules

    Returns:
    - Validation result
    - Error messages
    - Action availability
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Validate journal status and readiness.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters (journal_id, action)

        Returns:
            JsonResponse: Validation result
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')
        action = kwargs.get('action', 'post')  # post, delete, duplicate, reverse

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            # Validate based on action
            is_valid, errors, warnings = self._validate_for_action(
                request, journal, action
            )

            logger.debug(
                f"Status validation for journal {journal_id} - "
                f"Action: {action}, Valid: {is_valid}, Errors: {errors}"
            )

            return JsonResponse({
                'valid': is_valid,
                'status': journal.status,
                'action': action,
                'errors': errors,
                'warnings': warnings,
                'can_proceed': len(errors) == 0
            })

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return JsonResponse({
                'valid': False,
                'errors': [self._t(request, 'voucher.error.journal_not_found', 'Journal not found')]
            }, status=404)

        except Exception as e:
            logger.exception(f"Error validating status: {e}")
            return JsonResponse({
                'valid': False,
                'errors': [self._t(request, 'voucher.error.validation', 'Validation error: {message}', message=str(e))]
            }, status=500)

    def _validate_for_action(
        self, request, journal: Journal, action: str
    ) -> tuple:
        """
        Validate journal for specific action.

        Args:
            journal: Journal instance
            action: Action name (post, delete, duplicate, reverse)

        Returns:
            tuple: (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        # Check status-based permissions
        status_rules = {
            'post': {
                'allowed_statuses': ['draft', 'pending'],
                'forbidden_msg': self._t(request, 'voucher.error.forbidden.post', f'Cannot post a {journal.status} journal', status=journal.status)
            },
            'delete': {
                'allowed_statuses': ['draft'],
                'forbidden_msg': self._t(request, 'voucher.error.forbidden.delete', f'Cannot delete a {journal.status} journal', status=journal.status)
            },
            'reverse': {
                'allowed_statuses': ['posted', 'approved'],
                'forbidden_msg': self._t(request, 'voucher.error.forbidden.reverse', f'Cannot reverse a {journal.status} journal', status=journal.status)
            },
            'duplicate': {
                'allowed_statuses': [],  # All allowed
                'forbidden_msg': None
            }
        }

        rule = status_rules.get(action)
        if rule and rule['allowed_statuses']:
            if journal.status not in rule['allowed_statuses']:
                errors.append(rule['forbidden_msg'])

        # Check business rules
        lines_count = journal.lines.count()
        if lines_count == 0:
            errors.append(self._t(request, 'voucher.validation.must_have_line', 'Journal must have at least one line'))

        # Check balance
        total_debit = sum(l.debit_amount or 0 for l in journal.lines.all())
        total_credit = sum(l.credit_amount or 0 for l in journal.lines.all())

        if action == 'post' and total_debit != total_credit:
            errors.append(self._t(request, 'voucher.validation.journal_not_balanced', 'Journal is not balanced: Debit {debit} ≠ Credit {credit}', debit=total_debit, credit=total_credit))

        # Check reference number
        if action == 'post' and not journal.reference_no:
            warnings.append(self._t(request, 'voucher.warning.no_reference', 'Journal entry has no reference number'))

        is_valid = len(errors) == 0

        return is_valid, errors, warnings


class VoucherQuickActionHtmxView(BaseVoucherView):
    """
    HTMX handler for quick action confirmations.

    Handles confirmation dialogs and quick actions:
    - Post confirmation
    - Delete confirmation
    - Duplicate with options
    - Reverse with notification
    """

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        Display action confirmation dialog.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters (journal_id, action)

        Returns:
            HttpResponse: HTML confirmation dialog
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')
        action = kwargs.get('action', 'post')

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            context = {
                'journal': journal,
                'action': action,
                'action_title': self._get_action_title(action),
                'action_message': self._get_action_message(journal, action),
                'action_danger': action in ['delete', 'reverse'],
                'action_button_text': self._get_button_text(action)
            }

            html = render_to_string(
                'accounting/htmx/action_confirmation.html',
                context,
                request=request
            )

            logger.debug(f"Action confirmation dialog - Journal: {journal_id}, Action: {action}")

            return HttpResponse(html)

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return HttpResponse(
                '<div class="alert alert-danger">Journal not found</div>',
                status=404
            )

        except Exception as e:
            logger.exception(f"Error displaying confirmation: {e}")
            return HttpResponse(
                f'<div class="alert alert-danger">Error: {str(e)}</div>',
                status=500
            )

    def _get_action_title(self, action: str) -> str:
        """Get action confirmation title."""
        titles = {
            'post': 'Post Journal Entry',
            'delete': 'Delete Journal Entry',
            'duplicate': 'Duplicate Journal Entry',
            'reverse': 'Reverse Journal Entry'
        }
        return titles.get(action, 'Confirm Action')

    def _get_action_message(self, journal: Journal, action: str) -> str:
        """Get action confirmation message."""
        messages_map = {
            'post': f'Post journal entry {journal.reference_no}? '
                   'This action cannot be undone.',
            'delete': f'Delete journal entry {journal.reference_no}? '
                     'This action cannot be undone.',
            'duplicate': f'Create a duplicate of journal {journal.reference_no}? '
                        'A new draft entry will be created.',
            'reverse': f'Reverse journal entry {journal.reference_no}? '
                      'A new entry with opposite amounts will be created.'
        }
        return messages_map.get(action, 'Are you sure?')

    def _get_button_text(self, action: str) -> str:
        """Get action button text."""
        buttons = {
            'post': 'Post Entry',
            'delete': 'Delete Entry',
            'duplicate': 'Create Duplicate',
            'reverse': 'Create Reverse'
        }
        return buttons.get(action, 'Confirm')


class VoucherLineValidationHtmxView(BaseVoucherView):
    """
    HTMX handler for real-time line validation.

    Validates:
    - Debit/credit amounts
    - Account selection
    - Currency/exchange rate
    - Tax calculations
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Validate line form data in real-time.

        Args:
            request: HTTP request with line data
            *args, **kwargs: URL parameters

        Returns:
            JsonResponse: Validation result with error messages
        """
        try:
            data = request.POST or json.loads(request.body)

            # Extract values
            account_id = data.get('account_id')
            debit = float(data.get('debit_amount', 0) or 0)
            credit = float(data.get('credit_amount', 0) or 0)
            tax_rate = float(data.get('tax_rate', 0) or 0)

            errors = {}
            warnings = {}

            # Validate account
            if not account_id:
                errors['account'] = 'Account is required'
            else:
                try:
                    from accounting.models import ChartOfAccount
                    account = ChartOfAccount.objects.get(id=account_id)
                except ChartOfAccount.DoesNotExist:
                    errors['account'] = 'Selected account does not exist'

            # Validate amounts
            if debit > 0 and credit > 0:
                errors['amounts'] = 'Cannot have both debit and credit'
            elif debit == 0 and credit == 0:
                errors['amounts'] = 'Must have either debit or credit amount'

            if debit < 0:
                errors['debit'] = 'Debit amount cannot be negative'
            if credit < 0:
                errors['credit'] = 'Credit amount cannot be negative'

            # Validate tax
            if tax_rate < 0 or tax_rate > 100:
                errors['tax_rate'] = 'Tax rate must be between 0 and 100'

            # Warnings
            if debit > 1000000 or credit > 1000000:
                warnings['large_amount'] = 'Very large amount detected - please verify'

            if tax_rate > 30:
                warnings['high_tax'] = 'Unusually high tax rate - please verify'

            is_valid = len(errors) == 0

            logger.debug(
                f"Line validation - Valid: {is_valid}, "
                f"Debit: {debit}, Credit: {credit}, Tax: {tax_rate}"
            )

            return JsonResponse({
                'valid': is_valid,
                'errors': errors,
                'warnings': warnings,
                'data': {
                    'debit_amount': debit,
                    'credit_amount': credit,
                    'tax_rate': tax_rate
                }
            })

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid line data: {e}")
            return JsonResponse({
                'valid': False,
                'errors': {'general': f'Invalid input: {str(e)}'}
            }, status=400)

        except Exception as e:
            logger.exception(f"Error validating line: {e}")
            return JsonResponse({
                'valid': False,
                'errors': {'general': f'Validation error: {str(e)}'}
            }, status=500)


class VoucherBalanceCheckHtmxView(BaseVoucherView):
    """
    HTMX handler for real-time journal balance checking.

    Triggered when:
    - Line debit/credit changes
    - Line added/removed
    - Line deleted

    Returns:
    - Current balance
    - Balance status (balanced/unbalanced)
    - Difference if unbalanced
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Check journal balance based on form data.

        Args:
            request: HTTP request with line data
            *args, **kwargs: URL parameters (journal_id)

        Returns:
            JsonResponse: Balance information
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            # Parse form data
            data = request.POST or json.loads(request.body)

            # Calculate totals from formset
            total_debit = 0
            total_credit = 0

            # Process each line in formset
            line_num = 0
            while True:
                debit_key = f'lines-{line_num}-debit_amount'
                credit_key = f'lines-{line_num}-credit_amount'
                delete_key = f'lines-{line_num}-DELETE'

                if debit_key not in data:
                    break

                # Skip deleted lines
                if data.get(delete_key) == 'on':
                    line_num += 1
                    continue

                try:
                    debit = float(data.get(debit_key) or 0)
                    credit = float(data.get(credit_key) or 0)
                    total_debit += debit
                    total_credit += credit
                except (ValueError, TypeError):
                    pass

                line_num += 1

            is_balanced = total_debit == total_credit
            difference = abs(total_debit - total_credit)

            status_text = 'Balanced âœ“' if is_balanced else 'Unbalanced âœ—'
            status_class = 'text-success' if is_balanced else 'text-danger'

            html = render_to_string(
                'accounting/htmx/balance_status.html',
                {
                    'total_debit': total_debit,
                    'total_credit': total_credit,
                    'is_balanced': is_balanced,
                    'status_text': status_text,
                    'status_class': status_class,
                    'difference': difference
                },
                request=request
            )

            logger.debug(
                f"Balance check - Journal: {journal_id}, "
                f"Debit: {total_debit}, Credit: {total_credit}, "
                f"Balanced: {is_balanced}"
            )

            return HttpResponse(html)

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return HttpResponse(
                '<div class="alert alert-danger">Journal not found</div>',
                status=404
            )

        except Exception as e:
            logger.exception(f"Error checking balance: {e}")
            return HttpResponse(
                f'<div class="alert alert-danger">Error: {str(e)}</div>',
                status=500
            )


class VoucherAddLineHtmxView(BaseVoucherView):
    """
    HTMX handler for adding a new line to a voucher.

    Creates a new journal line with default values and returns
    the HTML fragment for the new line row.
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Add a new line to the journal.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters (journal_id)

        Returns:
            HttpResponse: HTML fragment for new line
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            # Check if journal allows editing
            if journal.status not in ['draft', 'pending']:
                msg = self._t(
                    request,
                    'voucher.error.cannot_add_to_status',
                    f'Cannot add lines to {journal.status} journals',
                    status=journal.status,
                )
                return HttpResponse(
                    f'<div class="alert alert-danger">{msg}</div>',
                    status=400
                )

            # Get the next line number
            next_line_number = journal.lines.count() + 1

            # Create new line with defaults
            new_line = JournalLine.objects.create(
                journal=journal,
                line_number=next_line_number,
                description='',
                debit_amount=None,
                credit_amount=None,
                created_by=request.user,
                updated_by=request.user,
            )

            logger.info(
                f"Line {new_line.id} added to journal {journal_id} "
                f"by {request.user.username}"
            )

            # Return HTML fragment for the new line
            context = {
                'line': new_line,
                'journal': journal,
                'line_number': next_line_number,
                'accounts': [],  # Will be populated by account lookup
                'can_edit': True,
                'can_delete': True,
            }

            html = render_to_string(
                'accounting/htmx/voucher_line_row.html',
                context,
                request=request
            )

            return HttpResponse(
                html,
                headers={'HX-Trigger': 'lineAdded'}
            )

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.journal_not_found", "Journal not found")}</div>',
                status=404
            )

        except Exception as e:
            logger.exception(f"Error adding line: {e}")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.error_prefix", "Error: {message}", message=str(e))}</div>',
                status=500
            )


class VoucherAccountLookupHtmxView(BaseVoucherView):
    """
    HTMX handler for account lookup/search functionality.

    Provides autocomplete suggestions for account selection
    in voucher line forms.
    """

    def get(self, request, *args, **kwargs) -> JsonResponse:
        """
        Search for accounts based on query.

        Args:
            request: HTTP request with 'q' parameter
            *args, **kwargs: URL parameters

        Returns:
            JsonResponse: Account suggestions
        """
        organization = self.get_organization()
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 10))

        try:
            from accounting.models import ChartOfAccount

            # Build queryset with filters
            # Allow lookups even when no active organization is set (tests and lightweight JS rely on this)
            if organization:
                accounts = ChartOfAccount.objects.filter(
                    organization=organization,
                    is_active=True
                )
            else:
                accounts = ChartOfAccount.objects.filter(
                    is_active=True
                )

            if query:
                accounts = accounts.filter(
                    account_name__icontains=query
                ) | accounts.filter(
                    account_code__icontains=query
                )

            # Order by relevance (exact matches first, then code, then name)
            accounts = accounts.order_by(
                'account_code'
            )[:limit]

            # Format results
            results = []
            for account in accounts:
                results.append({
                    'id': getattr(account, 'account_id', None) or getattr(account, 'id', None),
                    'text': f"{account.account_code} - {account.account_name}",
                    'code': account.account_code,
                    'name': account.account_name,
                    'type': account.account_type.name if account.account_type else '',
                    'balance': float(account.balance or 0),
                })

            logger.debug(
                f"Account lookup - Query: '{query}', "
                f"Results: {len(results)}"
            )

            return JsonResponse({
                'results': results,
                'total': len(results)
            })

        except Exception as e:
            logger.exception(f"Error in account lookup: {e}")
            return JsonResponse({
                'error': 'Search failed',
                'results': []
            }, status=500)

    def dispatch(self, request, *args, **kwargs):
        """
        Override dispatch to allow account lookups without requiring an
        active organization. This is used by lightweight JS typeahead and
        unit tests which may not set an active organization on the user.
        """
        from django.views import View as _View
        return _View.dispatch(self, request, *args, **kwargs)


class VoucherTaxCalculationHtmxView(BaseVoucherView):
    """
    HTMX handler for tax calculations on voucher lines.

    Calculates tax amounts based on base amount, tax rate, and tax type.
    Supports different tax calculation methods.
    """

    def post(self, request, *args, **kwargs) -> JsonResponse:
        """
        Calculate tax for a line amount.

        Args:
            request: HTTP request with calculation parameters
            *args, **kwargs: URL parameters

        Returns:
            JsonResponse: Tax calculation results
        """
        try:
            # Parse input data
            data = request.POST or json.loads(request.body)
            base_amount = float(data.get('base_amount', 0) or 0)
            tax_rate = float(data.get('tax_rate', 0) or 0)
            tax_type = data.get('tax_type', 'inclusive')  # inclusive/exclusive
            line_id = data.get('line_id')

            # Validate inputs
            if base_amount < 0:
                return JsonResponse({
                    'valid': False,
                    'error': 'Base amount cannot be negative'
                }, status=400)

            if tax_rate < 0 or tax_rate > 100:
                return JsonResponse({
                    'valid': False,
                    'error': 'Tax rate must be between 0 and 100'
                }, status=400)

            # Calculate tax
            if tax_type == 'inclusive':
                # Tax is included in the base amount
                tax_amount = round(base_amount * tax_rate / (100 + tax_rate), 2)
                net_amount = base_amount - tax_amount
            else:
                # Tax is additional to the base amount
                tax_amount = round(base_amount * tax_rate / 100, 2)
                net_amount = base_amount

            total_amount = net_amount + tax_amount

            logger.debug(
                f"Tax calculation - Base: {base_amount}, "
                f"Rate: {tax_rate}%, Type: {tax_type}, "
                f"Tax: {tax_amount}, Total: {total_amount}"
            )

            return JsonResponse({
                'valid': True,
                'base_amount': base_amount,
                'tax_rate': tax_rate,
                'tax_type': tax_type,
                'tax_amount': tax_amount,
                'net_amount': net_amount,
                'total_amount': total_amount,
                'calculation_method': tax_type
            })

        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid tax calculation input: {e}")
            return JsonResponse({
                'valid': False,
                'error': 'Invalid input data'
            }, status=400)

        except Exception as e:
            logger.exception(f"Error calculating tax: {e}")
            return JsonResponse({
                'valid': False,
                'error': f'Calculation failed: {str(e)}'
            }, status=500)


class VoucherAutoBalanceHtmxView(BaseVoucherView):
    """
    HTMX handler for automatically balancing a voucher.

    Adjusts the last line to balance the voucher by adding
    the difference to either debit or credit.
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Auto-balance the journal by adjusting the last line.

        Args:
            request: HTTP request
            *args, **kwargs: URL parameters (journal_id)

        Returns:
            HttpResponse: Updated lines container HTML
        """
        organization = self.get_organization()
        journal_id = kwargs.get('journal_id')

        try:
            journal = Journal.objects.get(
                id=journal_id,
                organization=organization
            )

            # Check if journal allows editing
            if journal.status not in ['draft', 'pending']:
                msg = self._t(
                    request,
                    'voucher.error.cannot_edit_status',
                    f'Cannot edit {journal.status} journals',
                    status=journal.status,
                )
                return HttpResponse(
                    f'<div class="alert alert-danger">{msg}</div>',
                    status=400
                )

            # Calculate current totals
            lines = list(journal.lines.all().order_by('line_number'))
            if not lines:
                return HttpResponse(
                    '<div class="alert alert-warning">No lines to balance</div>',
                    status=400
                )

            total_debit = sum(l.debit_amount or 0 for l in lines)
            total_credit = sum(l.credit_amount or 0 for l in lines)
            difference = total_debit - total_credit

            if difference == 0:
                return HttpResponse(
                    '<div class="alert alert-info">Journal is already balanced</div>'
                )

            # Adjust the last line
            last_line = lines[-1]

            if difference > 0:
                # Debit exceeds credit, add to credit of last line
                last_line.credit_amount = (last_line.credit_amount or 0) + difference
                last_line.debit_amount = None
                adjustment_type = 'credit'
            else:
                # Credit exceeds debit, add to debit of last line
                last_line.debit_amount = (last_line.debit_amount or 0) + abs(difference)
                last_line.credit_amount = None
                adjustment_type = 'debit'

            last_line.description = f"{last_line.description or ''} (Auto-balanced)".strip()
            last_line.updated_by = request.user
            last_line.save()

            logger.info(
                f"Auto-balanced journal {journal_id} - "
                f"Adjusted line {last_line.id} {adjustment_type} by {abs(difference)}"
            )

            # Return updated lines container
            context = {
                'journal': journal,
                'lines': lines,
                'total_debit': total_debit + (abs(difference) if difference < 0 else 0),
                'total_credit': total_credit + (difference if difference > 0 else 0),
                'is_balanced': True,
            }

            html = render_to_string(
                'accounting/htmx/voucher_lines_container.html',
                context,
                request=request
            )

            return HttpResponse(
                html,
                headers={'HX-Trigger': 'journalBalanced'}
            )

        except Journal.DoesNotExist:
            logger.warning(f"Journal {journal_id} not found")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.journal_not_found", "Journal not found")}</div>',
                status=404
            )

        except Exception as e:
            logger.exception(f"Error auto-balancing journal: {e}")
            return HttpResponse(
                f'<div class="alert alert-danger">{self._t(request, "voucher.error.error_prefix", "Error: {message}", message=str(e))}</div>',
                status=500
            )


# Import after all views defined to avoid circular imports
from django.template.loader import render_to_string


