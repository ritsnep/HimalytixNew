from django.db import transaction
from accounting.models import Journal, JournalLine

class BatchOperationService:
    @transaction.atomic
    def process_batch(self, operations, user):
        results = {
            'success': [],
            'failures': []
        }

        for operation in operations:
            try:
                if operation['type'] == 'post':
                    self._post_journal(operation['id'], user)
                elif operation['type'] == 'delete':
                    self._delete_journal(operation['id'], user)
                results['success'].append(operation['id'])
            except Exception as e:
                results['failures'].append({
                    'id': operation['id'],
                    'error': str(e)
                })

        return results