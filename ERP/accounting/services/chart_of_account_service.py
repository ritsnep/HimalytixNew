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
