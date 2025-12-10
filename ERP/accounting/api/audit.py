"""
REST API endpoints for Audit Log viewing and filtering.
Provides rich filtering by date range, user, model type, action, and organization.
"""

from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from rest_framework import viewsets, serializers, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from django_filters import rest_framework as django_filters

from accounting.models import AuditLog
from accounting.mixins import AuditLogPermissionChecker


class CanViewAuditLog(BasePermission):
    """Permission class to check audit log viewing rights."""
    
    message = "You do not have permission to view audit logs."
    
    def has_permission(self, request):
        return AuditLogPermissionChecker.can_view(request.user)


class CanExportAuditLog(BasePermission):
    """Permission class to check audit log export rights."""
    
    message = "You do not have permission to export audit logs."
    
    def has_permission(self, request):
        return AuditLogPermissionChecker.can_export(request.user)


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog with nested user and organization data."""
    
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True, allow_null=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'timestamp', 'user_name', 'user_email', 'organization_name',
            'action', 'action_display', 'content_type_name', 'object_id',
            'changes', 'details', 'ip_address', 'is_immutable',
        ]
        read_only_fields = fields


class AuditLogFilter(django_filters.FilterSet):
    """Advanced filtering for AuditLog queryset."""
    
    timestamp_from = django_filters.IsoDateTimeFilter(
        field_name='timestamp',
        lookup_expr='gte',
        label='Timestamp from'
    )
    timestamp_to = django_filters.IsoDateTimeFilter(
        field_name='timestamp',
        lookup_expr='lte',
        label='Timestamp to'
    )
    user = django_filters.CharFilter(
        field_name='user__username',
        lookup_expr='icontains',
        label='Username (partial match)'
    )
    action = django_filters.ChoiceFilter(
        choices=AuditLog.ACTION_CHOICES,
        label='Action type'
    )
    model = django_filters.CharFilter(
        field_name='content_type__model',
        lookup_expr='icontains',
        label='Model name'
    )
    
    class Meta:
        model = AuditLog
        fields = ['timestamp_from', 'timestamp_to', 'user', 'action', 'model', 'organization']


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing and exporting audit logs.
    
    Supports rich filtering:
    - Date range: ?timestamp_from=2025-01-01&timestamp_to=2025-01-31
    - User: ?user=john
    - Action: ?action=create
    - Model: ?model=invoice
    - Organization: ?organization=1
    - Search: ?search=keyword
    
    Includes summary and export endpoints.
    """
    
    queryset = AuditLog.objects.select_related('user', 'organization', 'content_type').order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanViewAuditLog]
    filterset_class = AuditLogFilter
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'user__email', 'details', 'ip_address']
    ordering_fields = ['timestamp', 'user', 'action']
    ordering = ['-timestamp']
    
    def get_queryset(self):
        """Scope queryset to current user's organization for non-superusers."""
        qs = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser:
            return qs
        
        # Non-superusers only see their organization's logs
        active_org = getattr(self.request, 'active_organization', None)
        if active_org:
            qs = qs.filter(organization=active_org)
        else:
            # Fallback to user's organization
            if hasattr(user, 'organization') and user.organization:
                qs = qs.filter(organization=user.organization)
        
        return qs
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, CanViewAuditLog])
    def summary(self, request):
        """
        Get audit log summary statistics.
        
        Returns:
        - total_events: Total number of audit events
        - by_action: Count breakdown by action type
        - by_user: Count breakdown by user
        - by_model: Count breakdown by model
        - period: Time period covered
        """
        from accounting.utils.audit_integrity import get_audit_summary
        
        qs = self.get_queryset()
        org = getattr(request, 'active_organization', None)
        
        # Get time period from query params
        days = request.query_params.get('days', 30)
        try:
            days = int(days)
        except ValueError:
            days = 30
        
        if org:
            summary = get_audit_summary(org, days=days)
        else:
            # Aggregate across all accessible orgs
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(timestamp__gte=cutoff)
            
            summary = {
                'total_events': qs.count(),
                'by_action': {},
                'by_user': {},
                'by_model': {},
                'period_days': days,
            }
            
            # Action breakdown
            for action in ['create', 'update', 'delete', 'export', 'print', 'approve', 'reject', 'post', 'sync']:
                count = qs.filter(action=action).count()
                if count > 0:
                    summary['by_action'][action] = count
            
            # User breakdown
            for user_id in qs.values_list('user_id', flat=True).distinct():
                if user_id:
                    user = qs.filter(user_id=user_id).first().user
                    summary['by_user'][str(user)] = qs.filter(user_id=user_id).count()
            
            # Model breakdown
            for ct_id in qs.values_list('content_type_id', flat=True).distinct():
                if ct_id:
                    ct = qs.filter(content_type_id=ct_id).first().content_type
                    summary['by_model'][ct.model] = qs.filter(content_type_id=ct_id).count()
        
        return Response(summary)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, CanExportAuditLog])
    def export(self, request):
        """
        Export audit logs as CSV.
        
        Query params:
        - timestamp_from: Start date (ISO format)
        - timestamp_to: End date (ISO format)
        - format: 'csv' or 'json' (default: csv)
        """
        import csv
        from django.http import HttpResponse
        
        qs = self.filter_queryset(self.get_queryset())
        format_type = request.query_params.get('format', 'csv').lower()
        
        if format_type == 'json':
            return self._export_json(qs)
        
        # CSV export
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'User', 'Organization', 'Action', 'Model', 'Object ID',
            'IP Address', 'Details', 'Immutable'
        ])
        
        for log in qs:
            writer.writerow([
                log.timestamp.isoformat(),
                str(log.user) if log.user else '',
                str(log.organization) if log.organization else '',
                log.get_action_display(),
                log.content_type.model if log.content_type else '',
                log.object_id,
                log.ip_address or '',
                log.details or '',
                'Yes' if log.is_immutable else 'No',
            ])
        
        return response
    
    def _export_json(self, qs):
        """Export audit logs as JSON."""
        from rest_framework.response import Response
        
        data = self.get_serializer(qs, many=True).data
        
        # Create JSON file response
        from django.http import HttpResponse
        import json
        
        response = HttpResponse(
            json.dumps(data, indent=2, default=str),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="audit_logs.json"'
        
        return response
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, CanViewAuditLog])
    def user_activity(self, request):
        """
        Get activity summary for a specific user.
        
        Query param:
        - user_id: User ID (required)
        - days: Number of days to look back (default: 7)
        """
        from accounting.utils.audit_integrity import get_user_activity
        from usermanagement.models import CustomUser
        
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': f'User {user_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        days = request.query_params.get('days', 7)
        try:
            days = int(days)
        except ValueError:
            days = 7
        
        active_org = getattr(request, 'active_organization', None)
        activity = get_user_activity(user, days=days, organization=active_org)
        
        return Response(activity)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, CanViewAuditLog])
    def entity_history(self, request):
        """
        Get full audit history for a specific entity.
        
        Query params:
        - model: Model name (e.g., 'invoice')
        - object_id: Entity's primary key
        """
        from django.contrib.contenttypes.models import ContentType
        from accounting.utils.audit_integrity import get_entity_history
        
        model_name = request.query_params.get('model')
        object_id = request.query_params.get('object_id')
        
        if not model_name or not object_id:
            return Response(
                {'error': 'model and object_id query parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            content_type = ContentType.objects.get(model=model_name.lower())
        except ContentType.DoesNotExist:
            return Response(
                {'error': f'Model {model_name} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            object_id = int(object_id)
        except ValueError:
            return Response(
                {'error': 'object_id must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        active_org = getattr(request, 'active_organization', None)
        history = get_entity_history(content_type, object_id, organization=active_org)
        
        serializer = self.get_serializer(history, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, CanExportAuditLog])
    def verify_integrity(self, request):
        """
        Verify integrity of audit log chain via hash-chaining.
        
        Request body:
        {
            "log_ids": [1, 2, 3],  # List of log IDs to verify
        }
        
        Returns:
        {
            "results": [
                {"log_id": 1, "valid": true},
                {"log_id": 2, "valid": false, "error": "..."}
            ],
            "valid_count": 1,
            "invalid_count": 1
        }
        """
        from accounting.utils.audit_integrity import verify_audit_chain
        
        log_ids = request.data.get('log_ids', [])
        if not log_ids:
            return Response(
                {'error': 'log_ids list is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = []
        valid_count = 0
        invalid_count = 0
        
        for log_id in log_ids:
            try:
                log = AuditLog.objects.get(id=log_id)
                is_valid, error_msg = verify_audit_chain(log)
                
                result = {'log_id': log_id, 'valid': is_valid}
                if error_msg:
                    result['error'] = error_msg
                
                results.append(result)
                
                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
            
            except AuditLog.DoesNotExist:
                results.append({
                    'log_id': log_id,
                    'valid': False,
                    'error': f'Log {log_id} not found'
                })
                invalid_count += 1
        
        return Response({
            'results': results,
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'total_checked': len(results),
        })
