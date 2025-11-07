from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from accounting.models import Journal, JournalLine
from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from usermanagement.utils import PermissionUtils
from accounting.services.post_journal import post_journal

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suggest_journal_entries(request):
    """
    Suggests journal entries based on historical data.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'view'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    suggestions = (
        Journal.objects.filter(organization=organization)
        .values('description')
        .annotate(count=Count('description'))
        .order_by('-count')[:5]
    )
    return Response([s['description'] for s in suggestions])

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_line_suggestions(request):
    """
    Suggests lines to complete an entry based on the provided description.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'view'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    description = request.GET.get('description')
    if not description:
        return Response([])

    lines = (
        JournalLine.objects.filter(
            journal__description=description,
            journal__organization=organization,
        )
        .values('account__account_code', 'account__account_name', 'debit_amount', 'credit_amount')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    
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
@permission_classes([IsAuthenticated])
def validate_field(request):
    """
    Validates a single field from the journal entry form.
    """
    organization = request.user.get_active_organization()
    if not organization:
        return Response({'detail': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
    if not PermissionUtils.has_permission(request.user, organization, 'accounting', 'journal', 'change'):
        return Response({'detail': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    field_name = request.data.get('field_name')
    field_value = request.data.get('field_value')
    
    # This is a simplified example. A real implementation would use a
    # form to validate the field and return the specific error message.
    if field_name == 'reference' and len(field_value) > 100:
        return Response({'error': 'Reference cannot be longer than 100 characters.'}, status=400)
        
    return Response({'success': True})

from rest_framework.views import APIView

class JournalBulkActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        journal_ids = request.data.get('journal_ids')

        if not action or not journal_ids:
            return Response({'error': 'Missing action or journal_ids'}, status=status.HTTP_400_BAD_REQUEST)

        organization = request.user.get_active_organization()
        if not organization:
            return Response({'error': 'Active organization required'}, status=status.HTTP_400_BAD_REQUEST)
        permission_map = {
            'post': ('accounting', 'journal', 'post_journal'),
            'delete': ('accounting', 'journal', 'delete'),
            'approve': ('accounting', 'journal', 'approve_journal'),
            'reject': ('accounting', 'journal', 'reject_journal'),
            'submit': ('accounting', 'journal', 'submit_journal'),
            'reverse': ('accounting', 'journal', 'reverse_journal'),
        }

        permission_tuple = permission_map.get(action)
        if permission_tuple and not PermissionUtils.has_permission(request.user, organization, *permission_tuple):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        journals = Journal.objects.filter(id__in=journal_ids, organization=organization)

        if action == 'delete':
            deleted_count = journals.delete()[0]
            return Response({'success': True, 'deleted': deleted_count})
        if action == 'post':
            posted = 0
            for journal in journals:
                if journal.status == 'approved':
                    post_journal(journal, request.user)
                    posted += 1
            return Response({'success': True, 'posted': posted})

        # Other actions would be implemented similarly

        return Response({'success': True, 'message': f'Action {action} acknowledged for {journals.count()} journals.'}, status=status.HTTP_200_OK)
