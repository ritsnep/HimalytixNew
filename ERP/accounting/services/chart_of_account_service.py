# Example: ChartOfAccountService for business logic
from accounting.models import ChartOfAccount
from accounting.repositories.chart_of_account_repository import ChartOfAccountRepository

class ChartOfAccountService:
    def __init__(self, repository=None):
        self.repository = repository or ChartOfAccountRepository()

    def create_account(self, data):
        # Add business rules here
        return self.repository.create(data)

    def get_account(self, pk):
        return self.repository.get(pk)

    def list_accounts(self, filters=None):
        return self.repository.list(filters or {})

    def update_account(self, pk, data):
        return self.repository.update(pk, data)

    def delete_account(self, pk):
        self.repository.delete(pk)

    def account_exists(self, **filters):
        return self.repository.exists(**filters)

    def all_accounts(self):
        return self.repository.all()

    @staticmethod
    def get_purchase_accounts_for_dropdown(organization):
        """
        Get purchase-related accounts for dropdown selection.
        """
        from accounting.models import AccountType
        purchase_account_types = AccountType.objects.filter(
            nature__in=['expense', 'asset']
        )
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            account_type__in=purchase_account_types,
            archived_at__isnull=True
        ).order_by('account_name')
        return [
            {'id': account.account_id, 'name': f"{account.account_code} - {account.account_name}"}
            for account in accounts
        ]

    @staticmethod
    def get_payment_ledgers_for_dropdown(organization):
        """
        Get cash/bank accounts for payment ledger dropdown.
        """
        from accounting.models import AccountType
        payment_account_types = AccountType.objects.filter(
            nature='asset'
        )
        accounts = ChartOfAccount.objects.filter(
            organization=organization,
            account_type__in=payment_account_types,
            account_code__regex=r'^(1000|1100|1200)',  # Cash/Bank account codes
            archived_at__isnull=True
        ).order_by('account_name')
        return [
            {'id': account.account_id, 'name': f"{account.account_code} - {account.account_name}"}
            for account in accounts
        ]
