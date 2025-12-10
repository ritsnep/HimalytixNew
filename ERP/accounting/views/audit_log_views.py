"""
Audit Log Views - User-friendly audit trail display using Dason template

Provides views for displaying audit logs in a professional, user-friendly interface
rather than the Django admin panel. Includes filtering, searching, and exporting capabilities.
"""

from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import csv
import json
from decimal import Decimal
from datetime import datetime

from accounting.models import AuditLog
from accounting.mixins import UserOrganizationMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType


class AuditLogListView(LoginRequiredMixin, UserOrganizationMixin, ListView):
    """
    Display audit logs in a user-friendly list view with filtering and search.
    
    Features:
    - Organization-scoped queries
    - Date range filtering
    - User filtering
    - Action type filtering
    - Search by model or object details
    - Pagination
    - CSV export
    """
    model = AuditLog
    template_name = 'accounting/audit_log_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    
    def get_queryset(self):
        """Get filtered audit logs."""
        organization = self.get_organization()
        queryset = AuditLog.objects.all()
        
        # Organization scoping
        # Include logs from the user's organization OR logs with no organization (legacy)
        if organization:
            queryset = queryset.filter(
                Q(organization=organization) | Q(organization__isnull=True)
            )
        elif not self.request.user.is_superuser:
            # Non-superusers only see their org logs or legacy logs
            if hasattr(self.request.user, 'organization'):
                queryset = queryset.filter(
                    Q(organization=self.request.user.organization) | Q(organization__isnull=True)
                )
        
        # Date range filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            try:
                from_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__gte=from_date)
            except (ValueError, TypeError):
                pass
        
        if date_to:
            try:
                to_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                # Include entire day
                to_date = timezone.datetime.combine(to_date, timezone.datetime.max.time()).date()
                queryset = queryset.filter(timestamp__date__lte=to_date)
            except (ValueError, TypeError):
                pass
        
        # User filtering
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Action filtering
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Search
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(details__icontains=search) |
                Q(user__username__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )
        
        # Prefetch related data for performance
        queryset = queryset.select_related(
            'user', 'organization', 'content_type'
        ).prefetch_related('previous_hash')
        
        return queryset.order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        # Get all users for this org for filtering
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if organization:
            # Get users in this organization
            users_in_org = User.objects.filter(
                organization=organization
            ).distinct()
        else:
            users_in_org = User.objects.all()
        
        context['users'] = users_in_org
        context['actions'] = AuditLog.ACTION_CHOICES
        context['current_action'] = self.request.GET.get('action', '')
        context['current_user'] = self.request.GET.get('user_id', '')
        context['current_search'] = self.request.GET.get('q', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        return context


class AuditLogDetailView(LoginRequiredMixin, UserOrganizationMixin, DetailView):
    """
    Display detailed view of a single audit log entry.
    
    Shows:
    - Full change details in a formatted view
    - Before/after comparison
    - User and IP information
    - Hash-chain verification status
    - Related transactions
    """
    model = AuditLog
    template_name = 'accounting/audit_log_detail.html'
    context_object_name = 'audit_log'
    
    def get_queryset(self):
        """Filter by organization."""
        organization = self.get_organization()
        queryset = AuditLog.objects.select_related(
            'user', 'organization', 'content_type', 'previous_hash'
        )
        
        # Include logs from the user's organization OR logs with no organization (legacy)
        if organization:
            queryset = queryset.filter(
                Q(organization=organization) | Q(organization__isnull=True)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Format changes for display."""
        context = super().get_context_data(**kwargs)
        audit_log = self.object
        
        # Format changes dict for better display
        formatted_changes = []
        if audit_log.changes:
            for field, change_data in audit_log.changes.items():
                if isinstance(change_data, dict) and 'old' in change_data and 'new' in change_data:
                    formatted_changes.append({
                        'field': field,
                        'old': change_data['old'],
                        'new': change_data['new'],
                    })
                else:
                    formatted_changes.append({
                        'field': field,
                        'value': change_data,
                    })
        
        context['formatted_changes'] = formatted_changes
        context['has_previous'] = audit_log.previous_hash_id is not None
        context['is_sealed'] = audit_log.is_immutable
        
        # Get content object if available
        try:
            context['content_object'] = audit_log.content_object
        except Exception:
            context['content_object'] = None
        
        return context


class AuditLogSummaryView(LoginRequiredMixin, UserOrganizationMixin, TemplateView):
    """
    Display summary statistics about audit logs.
    
    Shows:
    - Activity over time (charts)
    - Most active users
    - Most modified entities
    - Action breakdown
    - Recent suspicious activities
    """
    template_name = 'accounting/audit_log_summary.html'
    
    def get_context_data(self, **kwargs):
        """Gather summary statistics."""
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        # Base queryset
        base_qs = AuditLog.objects.all()
        if organization:
            # Include logs from the user's organization OR logs with no organization (legacy)
            base_qs = base_qs.filter(
                Q(organization=organization) | Q(organization__isnull=True)
            )
        
        # Date range
        days = int(self.request.GET.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        qs = base_qs.filter(timestamp__gte=since)
        
        # Statistics
        context['total_logs'] = qs.count()
        context['total_users'] = qs.values('user').distinct().count()
        context['total_entities'] = qs.values('content_type').distinct().count()
        context['date_range'] = days
        
        # Action breakdown
        context['action_breakdown'] = list(
            qs.values('action').annotate(count=Count('id')).order_by('-count')
        )
        
        # Most active users (last 30 days)
        context['active_users'] = list(
            qs.values('user__username', 'user__first_name').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
        )
        
        # Most modified models
        content_types = qs.values('content_type_id').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        modified_entities = []
        for ct_data in content_types:
            try:
                ct = ContentType.objects.get(id=ct_data['content_type_id'])
                modified_entities.append({
                    'model': ct.model,
                    'app': ct.app_label,
                    'count': ct_data['count']
                })
            except ContentType.DoesNotExist:
                pass
        
        context['modified_entities'] = modified_entities
        
        # Time-based activity (for charts)
        daily_activity = []
        for i in range(days, 0, -1):
            date = timezone.now().date() - timedelta(days=i)
            count = qs.filter(timestamp__date=date).count()
            daily_activity.append({
                'date': date.isoformat(),
                'count': count
            })
        
        context['daily_activity'] = json.dumps(daily_activity)
        context['daily_activity_json'] = daily_activity
        
        return context


def audit_log_export_csv(request):
    """Export audit logs to CSV."""
    organization = getattr(request, 'active_organization', None)
    
    # Get base queryset
    queryset = AuditLog.objects.all()
    if organization:
        queryset = queryset.filter(organization=organization)
    
    # Apply filters from request
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__gte=from_date)
        except (ValueError, TypeError):
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            to_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__lte=to_date)
        except (ValueError, TypeError):
            pass
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit-log-{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'User', 'Organization', 'Action', 'Model', 'Object ID',
        'Details', 'IP Address', 'Changes', 'Immutable'
    ])
    
    for log in queryset.order_by('-timestamp')[:10000]:  # Limit to 10k rows
        changes_json = json.dumps(log.changes) if log.changes else ''
        writer.writerow([
            log.timestamp.isoformat(),
            str(log.user) if log.user else '',
            str(log.organization) if log.organization else '',
            log.action,
            log.content_type.model if log.content_type else '',
            log.object_id,
            log.details or '',
            log.ip_address or '',
            changes_json,
            'Yes' if log.is_immutable else 'No'
        ])
    
    return response


def audit_log_export_json(request):
    """Export audit logs to JSON."""
    organization = getattr(request, 'active_organization', None)
    
    queryset = AuditLog.objects.all()
    if organization:
        queryset = queryset.filter(organization=organization)
    
    # Apply filters
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__gte=from_date)
        except (ValueError, TypeError):
            pass
    
    data = []
    for log in queryset.order_by('-timestamp')[:10000]:
        data.append({
            'id': log.id,
            'timestamp': log.timestamp.isoformat(),
            'user': str(log.user) if log.user else None,
            'organization': str(log.organization) if log.organization else None,
            'action': log.action,
            'model': log.content_type.model if log.content_type else None,
            'object_id': log.object_id,
            'details': log.details,
            'ip_address': log.ip_address,
            'changes': log.changes,
            'is_immutable': log.is_immutable,
        })
    
    response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="audit-log-{timezone.now().date()}.json"'
    
    return response
