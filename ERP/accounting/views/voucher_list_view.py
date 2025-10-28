"""
Voucher List View - Phase 2 Implementation

Displays paginated list of journal entries with:
- Filtering (status, period, type, date range)
- Sorting
- Search
- Pagination
- Organization context enforcement
- Bulk actions
"""

import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum, F, Count, Case, When, DecimalField
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.db import models

from accounting.models import Journal, JournalType, AccountingPeriod
from accounting.views.base_voucher_view import BaseVoucherView, VoucherListMixin

logger = logging.getLogger(__name__)


class VoucherListView(VoucherListMixin, BaseVoucherView, ListView):
    """
    View for listing journal entries with filtering and pagination.

    Handles:
    - List all journals for organization
    - Filter by status, period, type, date range
    - Search by reference or notes
    - Sort by various fields
    - Pagination
    - Bulk actions
    """

    model = Journal
    template_name = 'accounting/journal_entry_list.html'
    paginate_by = 25
    page_title = 'Journal Entries'

    # Filtering options
    STATUS_CHOICES = [
        ('', 'All Status'),
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('posted', 'Posted'),
        ('approved', 'Approved'),
    ]

    SORT_CHOICES = [
        ('date_desc', 'Date (Newest)'),
        ('date_asc', 'Date (Oldest)'),
        ('amount_desc', 'Amount (Highest)'),
        ('amount_asc', 'Amount (Lowest)'),
        ('status', 'Status'),
        ('type', 'Type'),
    ]

    def get_queryset(self) -> QuerySet:
        """
        Get filtered and sorted queryset.

        Handles:
        - Organization isolation
        - Status filtering
        - Period filtering
        - Type filtering
        - Date range filtering
        - Text search
        - Sorting

        Returns:
            QuerySet: Filtered and sorted journals
        """
        organization = self.get_organization()

        queryset = Journal.objects.filter(
            organization=organization
        ).select_related(
            'journal_type',
            'period',
            'organization'
        ).prefetch_related('lines')

        # Status filter
        status = self.request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)

        # Period filter
        period = self.request.GET.get('period', '')
        if period:
            queryset = queryset.filter(period_id=period)

        # Type filter
        journal_type = self.request.GET.get('type', '')
        if journal_type:
            queryset = queryset.filter(journal_type_id=journal_type)

        # Date range filter
        date_from = self.request.GET.get('date_from', '')
        if date_from:
            queryset = queryset.filter(journal_date__gte=date_from)

        date_to = self.request.GET.get('date_to', '')
        if date_to:
            queryset = queryset.filter(journal_date__lte=date_to)

        # Search filter
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(reference_no__icontains=search) |
                Q(notes__icontains=search)
            )

        # Sorting
        sort = self.request.GET.get('sort', 'date_desc')
        if sort == 'date_desc':
            queryset = queryset.order_by('-journal_date')
        elif sort == 'date_asc':
            queryset = queryset.order_by('journal_date')
        elif sort == 'amount_desc':
            queryset = queryset.order_by('-total_debit')
        elif sort == 'amount_asc':
            queryset = queryset.order_by('total_debit')
        elif sort == 'status':
            queryset = queryset.order_by('status', '-journal_date')
        elif sort == 'type':
            queryset = queryset.order_by('journal_type__name', '-journal_date')
        else:
            queryset = queryset.order_by('-journal_date')

            # REMOVED: Don't call .count() here - it triggers an extra database query
            # logger.debug(
            #     f"VoucherListView queryset - Organization: {organization.id}, "
            #     f"Filters: status={status}, period={period}, type={journal_type}, "
            #     f"search={search}, sort={sort}"
            # )

        return queryset

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """
        Build context with filter options and statistics.

        Args:
            **kwargs: Additional context

        Returns:
            Dict[str, Any]: Context for template
        """
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()

        # Get current filters for template
        current_filters = self._get_current_filters()

        # Get filter options
        periods = AccountingPeriod.objects.filter(
            organization=organization
        ).order_by('-end_date')

        journal_types = JournalType.objects.filter(
            organization=organization
        ).order_by('name')

        # OPTIMIZED: Get statistics with a SINGLE aggregation query instead of 6 separate queries
        all_journals = Journal.objects.filter(organization=organization)
        statistics = all_journals.aggregate(
            total=Count('id'),
            draft=Count('id', filter=Q(status='draft')),
            pending=Count('id', filter=Q(status='pending')),
            posted=Count('id', filter=Q(status='posted')),
            approved=Count('id', filter=Q(status='approved')),
            total_amount=Sum('total_debit', output_field=DecimalField(max_digits=15, decimal_places=2))
        )

        # Handle None values
        statistics['total_amount'] = statistics['total_amount'] or 0

        # OPTIMIZED: Get current queryset totals (reuse the evaluated list view queryset)
        # In ListView, self.object_list is set to the queryset before pagination
        queryset_totals = self.object_list.aggregate(
            total_debit=Sum('total_debit'),
            total_credit=Sum('total_credit'),
            count=Count('id')
        )

        # Build query string for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']
        query_string = query_params.urlencode()

        context.update({
            'status_choices': self.STATUS_CHOICES,
            'sort_choices': self.SORT_CHOICES,
            'current_filters': current_filters,
            'periods': periods,
            'journal_types': journal_types,
            'statistics': statistics,
            'queryset_totals': queryset_totals,
            'query_string': query_string,
            'has_filters': bool(current_filters['active_filters']),
        })

        logger.debug(f"VoucherListView context - {len(context['object_list'])} items")

        return context

    def _get_current_filters(self) -> Dict[str, Any]:
        """
        Get current filter values from request.

        Returns:
            Dict[str, Any]: Current filter values and active filter list
        """
        filters = {
            'status': self.request.GET.get('status', ''),
            'period': self.request.GET.get('period', ''),
            'type': self.request.GET.get('type', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'search': self.request.GET.get('search', ''),
            'sort': self.request.GET.get('sort', 'date_desc'),
        }

        # Determine which filters are active
        active_filters = [k for k, v in filters.items() if v and k != 'sort']

        filters['active_filters'] = active_filters
        filters['active_count'] = len(active_filters)

        return filters


class VoucherBulkActionView(BaseVoucherView):
    """
    View for handling bulk actions on journals.

    Supports:
    - Bulk delete (draft only)
    - Bulk post
    - Bulk status change
    """

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        Handle bulk action on selected journals.

        Args:
            request: HTTP request with action and selected IDs
            *args, **kwargs: URL parameters

        Returns:
            HttpResponse: Redirect to list view
        """
        from django.contrib import messages

        organization = self.get_organization()
        action = request.POST.get('bulk_action', '')
        selected_ids = request.POST.getlist('selected_journals')

        if not selected_ids:
            messages.warning(request, "No journals selected.")
            return redirect('accounting:journal_list')

        # Get selected journals
        journals = Journal.objects.filter(
            id__in=selected_ids,
            organization=organization
        )

        logger.debug(
            f"Bulk action '{action}' on {journals.count()} journals "
            f"by {request.user.username}"
        )

        success_count = 0
        error_count = 0

        try:
            if action == 'delete':
                success_count, error_count = self._bulk_delete(
                    journals, request
                )

            elif action == 'post':
                success_count, error_count = self._bulk_post(
                    journals, request
                )

            elif action == 'export':
                return self._bulk_export(journals)

            if success_count > 0:
                messages.success(
                    request,
                    f"Successfully {action}ed {success_count} journal(s)."
                )

            if error_count > 0:
                messages.warning(
                    request,
                    f"Failed to {action} {error_count} journal(s). "
                    f"Check logs for details."
                )

        except Exception as e:
            logger.exception(f"Error in bulk action: {e}")
            messages.error(request, "Error processing bulk action.")

        return redirect('accounting:journal_list')

    def _bulk_delete(self, journals, request) -> tuple:
        """
        Delete journals (draft only).

        Args:
            journals: QuerySet of journals
            request: HTTP request

        Returns:
            tuple: (success_count, error_count)
        """
        success_count = 0
        error_count = 0

        for journal in journals:
            try:
                if journal.status == 'draft':
                    journal.delete()
                    success_count += 1
                    logger.info(f"Journal {journal.id} deleted (bulk)")
                else:
                    logger.warning(
                        f"Cannot delete {journal.status} journal {journal.id}"
                    )
                    error_count += 1

            except Exception as e:
                logger.exception(f"Error deleting journal {journal.id}: {e}")
                error_count += 1

        return success_count, error_count

    def _bulk_post(self, journals, request) -> tuple:
        """
        Post journals.

        Args:
            journals: QuerySet of journals
            request: HTTP request

        Returns:
            tuple: (success_count, error_count)
        """
        success_count = 0
        error_count = 0

        for journal in journals:
            try:
                if journal.status in ['draft', 'pending']:
                    journal.status = 'posted'
                    journal.posted_by = request.user
                    journal.save()
                    success_count += 1
                    logger.info(f"Journal {journal.id} posted (bulk)")
                else:
                    logger.warning(
                        f"Cannot post {journal.status} journal {journal.id}"
                    )
                    error_count += 1

            except Exception as e:
                logger.exception(f"Error posting journal {journal.id}: {e}")
                error_count += 1

        return success_count, error_count

    def _bulk_export(self, journals):
        """
        Export journals to CSV.

        Args:
            journals: QuerySet of journals

        Returns:
            HttpResponse: CSV file
        """
        import csv
        from django.http import FileResponse
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Journal ID',
            'Reference',
            'Date',
            'Type',
            'Status',
            'Total Debit',
            'Total Credit',
            'Notes'
        ])

        # Write data
        for journal in journals:
            writer.writerow([
                journal.id,
                journal.reference_no,
                journal.journal_date,
                journal.journal_type.name,
                journal.status,
                journal.total_debit,
                journal.total_credit,
                journal.notes
            ])

        # Return as file
        output.seek(0)
        response = FileResponse(output, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="journals.csv"'

        logger.info(f"Exported {journals.count()} journals to CSV")

        return response


# (removed redundant import of models at EOF)
