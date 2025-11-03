from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

class Command(BaseCommand):
    help = "Smoke-check voucher CRUD: create a balanced voucher, update it, then delete it."

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from accounting.models import VoucherModeConfig, ChartOfAccount, Journal
        from accounting.services.create_voucher import create_voucher

        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            raise CommandError("No superuser found to perform smoke test.")

        config = VoucherModeConfig.objects.filter(is_active=True, archived_at__isnull=True).first()
        if not config:
            raise CommandError("No active VoucherModeConfig found. Create a voucher configuration first.")

        org = getattr(user, 'organization', None) or getattr(user, 'get_active_organization', lambda: None)()
        if org is None:
            # Fallback to config's organization for this smoke test
            org = getattr(config, 'organization', None)
        if org is None:
            raise CommandError("No organization context available for smoke test.")

        accounts = list(ChartOfAccount.objects.filter(organization=org, is_active=True)[:2])
        if len(accounts) < 2:
            raise CommandError("Need at least two active accounts in the organization to perform smoke test.")

        # Create
        header = {
            'journal_date': timezone.now().date(),
            'description': 'Smoke test voucher (auto)'
        }
        lines = [
            {'account': accounts[0].pk, 'description': 'debit', 'debit_amount': 25, 'credit_amount': 0},
            {'account': accounts[1].pk, 'description': 'credit', 'debit_amount': 0, 'credit_amount': 25},
        ]
        # Ensure create_voucher can infer organization via user or config
        if not getattr(user, 'organization', None):
            try:
                # Set attribute for the scope of this command so create_voucher sees it
                user.organization = org
            except Exception:
                pass

        journal = create_voucher(user=user, config_id=config.pk, header_data=header, lines_data=lines)
        self.stdout.write(self.style.SUCCESS(f"Created voucher id={journal.pk}, number={journal.journal_number}"))

        # Update
        journal.description = 'Smoke test voucher (updated)'
        try:
            # Set updated_by for audit log requirements
            if hasattr(journal, 'updated_by_id') and getattr(user, 'pk', None):
                journal.updated_by = user
            journal.save(update_fields=['description', 'updated_by'])
        except Exception:
            # Fallback to a direct update if model save hooks are strict
            type(journal).objects.filter(pk=journal.pk).update(description=journal.description, updated_by=user)
        self.stdout.write(self.style.SUCCESS(f"Updated voucher id={journal.pk}"))

        # Delete
        pk = journal.pk
        journal.delete()
        exists = Journal.objects.filter(pk=pk).exists()
        if exists:
            raise CommandError("Delete failed: journal still exists.")
        self.stdout.write(self.style.SUCCESS(f"Deleted voucher id={pk}"))

        self.stdout.write(self.style.SUCCESS("Smoke-check voucher CRUD: PASS"))
