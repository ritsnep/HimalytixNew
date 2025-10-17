from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.contrib import messages
from django.db import transaction
from accounting.models import Journal, JournalLine

class JournalDuplicateView(View):
    def get(self, request, pk):
        original_journal = get_object_or_404(Journal, pk=pk)

        with transaction.atomic():
            new_journal = Journal.objects.create(
                organization=original_journal.organization,
                journal_type=original_journal.journal_type,
                period=original_journal.period,
                journal_date=original_journal.journal_date,
                reference=f"Copy of {original_journal.reference}",
                description=original_journal.description,
                currency_code=original_journal.currency_code,
                exchange_rate=original_journal.exchange_rate,
                status='draft',
                created_by=request.user,
            )

            for line in original_journal.lines.all():
                JournalLine.objects.create(
                    journal=new_journal,
                    line_number=line.line_number,
                    account=line.account,
                    description=line.description,
                    debit_amount=line.debit_amount,
                    credit_amount=line.credit_amount,
                    currency_code=line.currency_code,
                    exchange_rate=line.exchange_rate,
                    department=line.department,
                    project=line.project,
                    cost_center=line.cost_center,
                    tax_code=line.tax_code,
                    tax_rate=line.tax_rate,
                    tax_amount=line.tax_amount,
                    memo=line.memo,
                    created_by=request.user,
                )
        
        messages.success(request, "Journal duplicated successfully.")
        return redirect('accounting:journal_detail', pk=new_journal.pk)

class JournalReverseView(View):
    def get(self, request, pk):
        original_journal = get_object_or_404(Journal, pk=pk)

        if original_journal.status != 'posted':
            messages.error(request, "Only posted journals can be reversed.")
            return redirect('accounting:journal_detail', pk=pk)

        with transaction.atomic():
            new_journal = Journal.objects.create(
                organization=original_journal.organization,
                journal_type=original_journal.journal_type,
                period=original_journal.period,
                journal_date=original_journal.journal_date,
                reference=f"Reversal of {original_journal.reference}",
                description=f"Reversal of {original_journal.description}",
                currency_code=original_journal.currency_code,
                exchange_rate=original_journal.exchange_rate,
                status='draft',
                created_by=request.user,
                is_reversal=True,
            )

            for line in original_journal.lines.all():
                JournalLine.objects.create(
                    journal=new_journal,
                    line_number=line.line_number,
                    account=line.account,
                    description=line.description,
                    debit_amount=line.credit_amount,  # Reversed
                    credit_amount=line.debit_amount,  # Reversed
                    currency_code=line.currency_code,
                    exchange_rate=line.exchange_rate,
                    department=line.department,
                    project=line.project,
                    cost_center=line.cost_center,
                    tax_code=line.tax_code,
                    tax_rate=line.tax_rate,
                    tax_amount=line.tax_amount,
                    memo=line.memo,
                    created_by=request.user,
                )
        
        messages.success(request, "Journal reversed successfully.")
        return redirect('accounting:journal_detail', pk=new_journal.pk)