"""
Complete CRUD views for Voucher/Wizard-based journal entry system.
This provides a fresh, modern interface separate from the traditional journal_entry.html
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Prefetch
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from accounting.models import (
    Journal, JournalLine, VoucherModeConfig, 
    AccountingPeriod, JournalType
)
from accounting.views.views_mixins import UserOrganizationMixin, PermissionRequiredMixin
from accounting.forms_factory import FormBuilder
from accounting.services.create_voucher import create_voucher
from usermanagement.utils import PermissionUtils


class VoucherListView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    """
    List all journals created through the voucher wizard system.
    Provides filtering, search, and quick actions.
    """
    model = Journal
    template_name = 'accounting/vouchers/voucher_list.html'
    context_object_name = 'vouchers'
    permission_required = ('accounting', 'journal', 'view')
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'journal_type', 'period', 'created_by', 'posted_by', 'updated_by'
        ).order_by('-journal_date', '-created_at')

        # Apply search
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(journal_number__icontains=search) |
                Q(description__icontains=search) |
                Q(reference__icontains=search)
            )

        # Filter by status
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

        # Filter by journal type
        journal_type = self.request.GET.get('journal_type')
        if journal_type:
            queryset = queryset.filter(journal_type_id=journal_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        context.update({
            'page_title': 'Voucher Entries',
            'journal_types': JournalType.objects.filter(organization=organization),
            'statuses': Journal.STATUS_CHOICES,
            'can_create': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'add'),
            'can_edit': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'change'),
            'can_delete': PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'delete'),
        })
        return context


class VoucherDetailView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Display detailed view of a voucher with all lines, UDFs, and actions.
    Modern interface with keyboard shortcuts and command palette.
    """
    model = Journal
    template_name = 'accounting/vouchers/voucher_detail.html'
    context_object_name = 'voucher'
    permission_required = ('accounting', 'journal', 'view')

    def get_queryset(self):
        return super().get_queryset().select_related(
            'journal_type', 'period', 'created_by', 'posted_by', 'updated_by'
        ).prefetch_related(
            Prefetch('lines', queryset=JournalLine.objects.select_related('account', 'department', 'project', 'cost_center'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voucher = self.object
        organization = self.get_organization()
        
        # Calculate totals
        lines = voucher.lines.all()
        total_debit = sum(line.debit_amount or 0 for line in lines)
        total_credit = sum(line.credit_amount or 0 for line in lines)
        
        context.update({
            'page_title': f'Voucher {voucher.journal_number}',
            'total_debit': total_debit,
            'total_credit': total_credit,
            'is_balanced': abs(total_debit - total_credit) < 0.01,
            'can_edit': (
                voucher.status == 'draft' and 
                PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'change')
            ),
            'can_delete': (
                voucher.status == 'draft' and 
                PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'delete')
            ),
            'can_post': (
                voucher.status == 'draft' and
                PermissionUtils.has_permission(self.request.user, organization, 'accounting', 'journal', 'post_journal')
            ),
        })
        return context


class VoucherDeleteView(PermissionRequiredMixin, UserOrganizationMixin, DeleteView):
    """
    Delete a voucher (only if in draft status).
    """
    model = Journal
    template_name = 'accounting/vouchers/voucher_confirm_delete.html'
    success_url = reverse_lazy('accounting:voucher_list')
    permission_required = ('accounting', 'journal', 'delete')

    def get_queryset(self):
        return super().get_queryset().filter(status='draft')

    def delete(self, request, *args, **kwargs):
        voucher = self.get_object()
        
        if voucher.status != 'draft':
            messages.error(request, "Only draft vouchers can be deleted.")
            return redirect('accounting:voucher_detail', pk=voucher.pk)
        
        messages.success(request, f"Voucher {voucher.journal_number} has been deleted.")
        return super().delete(request, *args, **kwargs)


class VoucherDuplicateView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Duplicate an existing voucher as a new draft entry.
    """
    model = Journal
    permission_required = ('accounting', 'journal', 'add')

    def post(self, request, *args, **kwargs):
        source_voucher = self.get_object()
        organization = self.get_organization()
        
        # Create new voucher as copy
        new_voucher = Journal.objects.create(
            organization=organization,
            journal_type=source_voucher.journal_type,
            period=source_voucher.period,
            journal_date=timezone.now().date(),
            description=f"Copy of {source_voucher.description}",
            reference=source_voucher.reference,
            status='draft',
            created_by=request.user,
            updated_by=request.user,
            udf_data=source_voucher.udf_data,
        )
        
        # Copy all lines
        for line in source_voucher.lines.all():
            JournalLine.objects.create(
                journal=new_voucher,
                account=line.account,
                description=line.description,
                debit_amount=line.debit_amount,
                credit_amount=line.credit_amount,
                department=line.department,
                project=line.project,
                cost_center=line.cost_center,
                udf_data=line.udf_data,
            )
        
        # Update totals
        new_voucher.update_totals()
        new_voucher.save()
        
        messages.success(request, f"Voucher duplicated as {new_voucher.journal_number}")
        return redirect('accounting:voucher_wizard_edit', pk=new_voucher.pk)


class VoucherPostView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Post a draft voucher to the general ledger.
    """
    model = Journal
    permission_required = ('accounting', 'journal', 'post_journal')

    def post(self, request, *args, **kwargs):
        voucher = self.get_object()
        
        if voucher.status != 'draft':
            messages.error(request, "Only draft vouchers can be posted.")
            return redirect('accounting:voucher_detail', pk=voucher.pk)
        
        try:
            from accounting.services.post_journal import post_journal, JournalPostingError, JournalValidationError
            post_journal(voucher, request.user)
            messages.success(request, f"Voucher {voucher.journal_number} has been posted successfully.")
        except (JournalPostingError, JournalValidationError) as e:
            messages.error(request, f"Error posting voucher: {str(e)}")
        except Exception:
            messages.error(request, "Unexpected error while posting voucher.")
        
        return redirect('accounting:voucher_detail', pk=voucher.pk)


class VoucherPrintView(PermissionRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Generate printable version of voucher.
    """
    model = Journal
    template_name = 'accounting/vouchers/voucher_print.html'
    context_object_name = 'voucher'
    permission_required = ('accounting', 'journal', 'view')

    def get_queryset(self):
        return super().get_queryset().select_related(
            'journal_type', 'period', 'created_by', 'posted_by'
        ).prefetch_related('lines__account')


class VoucherExportView(PermissionRequiredMixin, UserOrganizationMixin, ListView):
    """
    Export vouchers to Excel/CSV.
    """
    model = Journal
    permission_required = ('accounting', 'journal', 'view')

    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vouchers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Journal Number', 'Date', 'Type', 'Reference', 'Description',
            'Status', 'Total Debit', 'Total Credit'
        ])
        
        vouchers = self.get_queryset()
        for voucher in vouchers:
            writer.writerow([
                voucher.journal_number,
                voucher.journal_date,
                voucher.journal_type.name if voucher.journal_type else '',
                voucher.reference or '',
                voucher.description or '',
                voucher.get_status_display(),
                voucher.total_debit,
                voucher.total_credit,
            ])
        
        return response
