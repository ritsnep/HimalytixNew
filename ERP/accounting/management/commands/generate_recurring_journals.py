from django.core.management.base import BaseCommand
from django.utils import timezone
from accounting.models import RecurringJournal, Journal, JournalLine
from django.db import transaction

class Command(BaseCommand):
    help = 'Generates journal entries from recurring journal templates'

    def handle(self, *args, **options):
        today = timezone.now().date()
        recurring_journals = RecurringJournal.objects.filter(next_run_date__lte=today, status='active')

        for rj in recurring_journals:
            with transaction.atomic():
                journal = Journal.objects.create(
                    organization=rj.organization,
                    journal_type=rj.journal_type,
                    period=rj.period,
                    journal_date=today,
                    reference=f"Recurring: {rj.name}",
                    description=rj.description,
                    currency_code=rj.currency_code,
                    exchange_rate=rj.exchange_rate,
                    status='draft',
                    created_by=rj.created_by,
                )

                for line in rj.lines.all():
                    JournalLine.objects.create(
                        journal=journal,
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
                        created_by=rj.created_by,
                    )
                
                rj.last_run_date = today
                # Calculate next run date based on frequency
                # This is a simplified example, a more robust solution would use dateutil.relativedelta
                if rj.frequency == 'monthly':
                    rj.next_run_date = today + timezone.timedelta(days=30)
                elif rj.frequency == 'quarterly':
                    rj.next_run_date = today + timezone.timedelta(days=90)
                elif rj.frequency == 'annually':
                    rj.next_run_date = today + timezone.timedelta(days=365)
                
                rj.save()

            self.stdout.write(self.style.SUCCESS(f'Successfully generated journal for "{rj.name}"'))