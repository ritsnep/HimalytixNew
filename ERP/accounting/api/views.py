from rest_framework.decorators import api_view
from rest_framework.response import Response
from accounting.models import Journal, JournalLine
from django.db.models import Count

@api_view(['GET'])
def suggest_journal_entries(request):
    """
    Suggests journal entries based on historical data.
    """
    # A simple suggestion engine: find the most common journal descriptions
    suggestions = Journal.objects.values('description').annotate(count=Count('description')).order_by('-count')[:5]
    return Response([s['description'] for s in suggestions])

@api_view(['GET'])
def get_line_suggestions(request):
    """
    Suggests lines to complete an entry based on the provided description.
    """
    description = request.GET.get('description')
    if not description:
        return Response([])

    # A simple suggestion engine: find the most common lines for a given description
    lines = JournalLine.objects.filter(journal__description=description).values('account__account_code', 'account__account_name', 'debit_amount', 'credit_amount').annotate(count=Count('id')).order_by('-count')[:5]
    
    suggestions = []
    for line in lines:
        suggestions.append({
            'account_code': line['account__account_code'],
            'account_name': line['account__account_name'],
            'debit_amount': line['debit_amount'],
            'credit_amount': line['credit_amount'],
        })

    return Response(suggestions)

@api_view(['POST'])
def validate_field(request):
    """
    Validates a single field from the journal entry form.
    """
    field_name = request.data.get('field_name')
    field_value = request.data.get('field_value')
    
    # This is a simplified example. A real implementation would use a
    # form to validate the field and return the specific error message.
    if field_name == 'reference' and len(field_value) > 100:
        return Response({'error': 'Reference cannot be longer than 100 characters.'}, status=400)
        
    return Response({'success': True})

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class JournalBulkActionView(APIView):
    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        journal_ids = request.data.get('journal_ids')

        if not action or not journal_ids:
            return Response({'error': 'Missing action or journal_ids'}, status=status.HTTP_400_BAD_REQUEST)

        # Placeholder for actual bulk action logic
        # In a real scenario, you would perform operations like:
        # if action == 'post':
        #     Journal.objects.filter(id__in=journal_ids).update(status='posted')
        # elif action == 'delete':
        #     Journal.objects.filter(id__in=journal_ids).delete()

        return Response({'success': True, 'message': f'Successfully performed {action} on {len(journal_ids)} journals.'}, status=status.HTTP_200_OK)