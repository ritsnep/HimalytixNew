# Example: ChartOfAccountRepository for data access
from accounting.models import ChartOfAccount

class ChartOfAccountRepository:
    def create(self, data):
        return ChartOfAccount.objects.create(**data)

    def list(self, filters):
        return ChartOfAccount.objects.filter(**filters)

    def update(self, pk, data):
        obj = ChartOfAccount.objects.get(pk=pk)
        for k, v in data.items():
            setattr(obj, k, v)
        obj.save()
        return obj

    def delete(self, pk):
        ChartOfAccount.objects.filter(pk=pk).delete()

    def get(self, pk):
        """Retrieve a single ChartOfAccount by primary key."""
        return ChartOfAccount.objects.get(pk=pk)

    def exists(self, **filters):
        """Check if any ChartOfAccount exists matching filters."""
        return ChartOfAccount.objects.filter(**filters).exists()

    def all(self):
        """Return all ChartOfAccount objects."""
        return ChartOfAccount.objects.all()
