# service_management/api/views.py
"""
REST API ViewSets for Service Management features
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone

from ..models import (
    DeviceCategory, DeviceModel, DeviceLifecycle, DeviceStateHistory,
    ServiceContract, ServiceTicket, WarrantyPool, RMAHardware,
    DeviceProvisioningTemplate, DeviceProvisioningLog
)
from .serializers import (
    DeviceCategorySerializer, DeviceModelSerializer, DeviceLifecycleSerializer,
    DeviceStateHistorySerializer, ServiceContractSerializer, ServiceTicketSerializer,
    WarrantyPoolSerializer, RMAHardwareSerializer, DeviceProvisioningTemplateSerializer,
    DeviceProvisioningLogSerializer
)
from api.permissions import IsOrganizationMember


class BaseServiceViewSet(viewsets.ModelViewSet):
    """Base viewset with organization filtering"""
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user.organization)
    
    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            created_by=self.request.user.id,
            updated_by=self.request.user.id
        )
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user.id)


class DeviceCategoryViewSet(BaseServiceViewSet):
    queryset = DeviceCategory.objects.all()
    serializer_class = DeviceCategorySerializer
    search_fields = ['code', 'name']
    filterset_fields = ['is_active']


class DeviceModelViewSet(BaseServiceViewSet):
    queryset = DeviceModel.objects.select_related('category')
    serializer_class = DeviceModelSerializer
    search_fields = ['model_number', 'model_name', 'manufacturer']
    filterset_fields = ['category', 'manufacturer', 'is_active']
    ordering_fields = ['model_number', 'model_name', 'created_at']


class DeviceLifecycleViewSet(BaseServiceViewSet):
    queryset = DeviceLifecycle.objects.select_related('device_model').prefetch_related('state_history')
    serializer_class = DeviceLifecycleSerializer
    search_fields = ['serial_number', 'customer_id']
    filterset_fields = ['device_model', 'customer_id', 'state']
    ordering_fields = ['deployed_date', 'warranty_start_date', 'created_at']
    
    @action(detail=False, methods=['get'])
    def warranty_expiring(self, request):
        """Get devices with warranty expiring soon"""
        from datetime import timedelta
        now = timezone.now().date()
        thirty_days = now + timedelta(days=30)
        
        expiring = self.get_queryset().filter(
            warranty_end_date__gte=now,
            warranty_end_date__lte=thirty_days,
            state__in=['deployed', 'active']
        )
        return Response(DeviceLifecycleSerializer(expiring, many=True).data)
    
    @action(detail=False, methods=['get'])
    def by_state(self, request):
        """Get device count by state"""
        state_counts = self.get_queryset().values('state').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response(state_counts)
    
    @action(detail=True, methods=['post'])
    def change_state(self, request, pk=None):
        """Change device state with history tracking"""
        device = self.get_object()
        new_state = request.data.get('new_state')
        reason = request.data.get('reason', '')
        
        if not new_state:
            return Response({'error': 'new_state is required'}, status=400)
        
        # Record state change
        DeviceStateHistory.objects.create(
            device=device,
            from_state=device.state,
            to_state=new_state,
            changed_by=request.user.id,
            reason=reason
        )
        
        device.state = new_state
        device.updated_by = request.user.id
        device.save()
        
        return Response(DeviceLifecycleSerializer(device).data)


class DeviceStateHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to device state history"""
    queryset = DeviceStateHistory.objects.select_related('device')
    serializer_class = DeviceStateHistorySerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filterset_fields = ['device', 'from_state', 'to_state']
    ordering_fields = ['changed_at']
    
    def get_queryset(self):
        return self.queryset.filter(device__organization=self.request.user.organization)


class ServiceContractViewSet(BaseServiceViewSet):
    queryset = ServiceContract.objects.all()
    serializer_class = ServiceContractSerializer
    search_fields = ['contract_number', 'customer_id']
    filterset_fields = ['customer_id', 'contract_type']
    ordering_fields = ['start_date', 'end_date', 'contract_value']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active service contracts"""
        now = timezone.now().date()
        active_contracts = self.get_queryset().filter(
            start_date__lte=now,
            end_date__gte=now
        )
        return Response(ServiceContractSerializer(active_contracts, many=True).data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get contracts expiring in the next 30 days"""
        from datetime import timedelta
        now = timezone.now().date()
        thirty_days = now + timedelta(days=30)
        
        expiring = self.get_queryset().filter(
            end_date__gte=now,
            end_date__lte=thirty_days,
            is_auto_renew=False
        )
        return Response(ServiceContractSerializer(expiring, many=True).data)


class ServiceTicketViewSet(BaseServiceViewSet):
    queryset = ServiceTicket.objects.select_related('service_contract', 'device')
    serializer_class = ServiceTicketSerializer
    search_fields = ['ticket_number', 'subject', 'description']
    filterset_fields = ['status', 'priority', 'service_contract', 'device', 'sla_breach']
    ordering_fields = ['created_date', 'priority', 'resolution_date']
    
    @action(detail=False, methods=['get'])
    def open(self, request):
        """Get open tickets"""
        open_tickets = self.get_queryset().filter(
            status__in=['open', 'in_progress']
        ).order_by('priority', 'reported_date')
        return Response(ServiceTicketSerializer(open_tickets, many=True).data)
    
    @action(detail=False, methods=['get'])
    def sla_breached(self, request):
        """Get tickets with SLA breaches"""
        now = timezone.now()
        breached = self.get_queryset().filter(
            Q(status__in=['open', 'in_progress']),
            Q(sla_resolution_due__lt=now)
        )
        return Response(ServiceTicketSerializer(breached, many=True).data)
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Get service ticket metrics"""
        tickets = self.get_queryset()
        
        total = tickets.count()
        by_status = tickets.values('status').annotate(count=Count('id'))
        by_priority = tickets.values('priority').annotate(count=Count('id'))
        
        # Calculate average resolution time
        resolved = tickets.filter(resolved_date__isnull=False)
        if resolved.exists():
            avg_resolution_hours = sum([
                (t.resolved_date - t.reported_date).total_seconds() / 3600
                for t in resolved
            ]) / resolved.count()
        else:
            avg_resolution_hours = 0
        
        return Response({
            'total_tickets': total,
            'by_status': list(by_status),
            'by_priority': list(by_priority),
            'average_resolution_hours': round(avg_resolution_hours, 2)
        })
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ticket to technician"""
        ticket = self.get_object()
        assigned_to = request.data.get('assigned_to')
        
        if not assigned_to:
            return Response({'error': 'assigned_to is required'}, status=400)
        
        ticket.assigned_to = assigned_to
        if ticket.status == 'open':
            ticket.status = 'in_progress'
            ticket.acknowledged_date = timezone.now()
        ticket.updated_by = request.user.id
        ticket.save()
        
        return Response(ServiceTicketSerializer(ticket).data)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve ticket"""
        ticket = self.get_object()
        resolution_notes = request.data.get('resolution_notes', '')
        root_cause = request.data.get('root_cause', '')
        
        ticket.status = 'resolved'
        ticket.resolved_date = timezone.now()
        ticket.resolution_notes = resolution_notes
        ticket.root_cause = root_cause
        ticket.updated_by = request.user.id
        ticket.save()
        
        return Response(ServiceTicketSerializer(ticket).data)


class WarrantyPoolViewSet(BaseServiceViewSet):
    queryset = WarrantyPool.objects.select_related('device_model')
    serializer_class = WarrantyPoolSerializer
    search_fields = ['pool_number', 'policy_number', 'provider_name']
    filterset_fields = ['device_model']
    
    @action(detail=False, methods=['get'])
    def near_limit(self, request):
        """Get warranty pools near claim limit"""
        pools = self.get_queryset().filter(
            max_claims__isnull=False
        )
        
        near_limit = [
            p for p in pools
            if p.max_claims > 0 and (p.claims_used / p.max_claims) > 0.8
        ]
        
        return Response(WarrantyPoolSerializer(near_limit, many=True).data)


class RMAHardwareViewSet(BaseServiceViewSet):
    queryset = RMAHardware.objects.select_related(
        'device', 
        'service_contract', 
        'service_ticket', 
        'replacement_device'
    )
    serializer_class = RMAHardwareSerializer
    search_fields = ['rma_number', 'warranty_claim_number', 'return_tracking_number', 'replacement_tracking_number']
    filterset_fields = ['status', 'failure_type', 'is_under_warranty', 'repair_action']
    ordering_fields = ['requested_date', 'status', 'completed_date']
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get RMAs pending approval"""
        pending = self.get_queryset().filter(status='pending')
        return Response(RMAHardwareSerializer(pending, many=True).data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve RMA"""
        rma = self.get_object()
        
        if rma.status != 'pending':
            return Response({'error': 'Only pending RMAs can be approved'}, status=400)
        
        rma.status = 'approved'
        rma.approved_date = timezone.now().date()
        rma.updated_by = request.user.id
        rma.save()
        
        # Update warranty pool if warranty claim
        if rma.is_warranty_claim and rma.warranty_pool:
            pool = rma.warranty_pool
            pool.claims_used += 1
            pool.save()
        
        return Response(RMAHardwareSerializer(rma).data)


class DeviceProvisioningTemplateViewSet(BaseServiceViewSet):
    queryset = DeviceProvisioningTemplate.objects.select_related('device_model')
    serializer_class = DeviceProvisioningTemplateSerializer
    search_fields = ['template_name']
    filterset_fields = ['device_model', 'is_active']


class DeviceProvisioningLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to provisioning logs"""
    queryset = DeviceProvisioningLog.objects.select_related('device', 'template')
    serializer_class = DeviceProvisioningLogSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filterset_fields = ['device', 'template', 'status']
    ordering_fields = ['provisioned_date']
    
    def get_queryset(self):
        return self.queryset.filter(organization=self.request.user.organization)
