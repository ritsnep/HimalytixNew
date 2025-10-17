from celery import shared_task
from .models import RecurringJournal
from .services.create_voucher import create_voucher
from datetime import date

@shared_task
def generate_recurring_journals():
    today = date.today()
    recurring_journals = RecurringJournal.objects.filter(is_active=True, start_date__lte=today)

    for rj in recurring_journals:
        if rj.end_date and rj.end_date < today:
            rj.is_active = False
            rj.save()
            continue

        if rj.last_run_date and rj.last_run_date.month == today.month and rj.last_run_date.year == today.year:
            continue

        # Create a new journal entry based on the recurring journal
        journal = rj.journal
        header_data = {
            'journal_date': today,
            'reference': f'Recurring: {journal.reference}',
            'description': journal.description,
        }
        lines_data = []
        for line in journal.journal_lines.all():
            lines_data.append({
                'account': line.account.pk,
                'debit_amount': line.debit_amount,
                'credit_amount': line.credit_amount,
                'description': line.description,
            })
        
        create_voucher(
            user=journal.created_by,
            config_id=journal.journal_type.voucher_config.pk,
            header_data=header_data,
            lines_data=lines_data,
            status='draft'
        )

        rj.last_run_date = today
        rj.save()