# billing/api/views.py
"""
REST API ViewSets for Billing/Subscription features
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, F
from django.utils import timezone

from ..models import (
    SubscriptionPlan, UsageTier, Subscription, SubscriptionUsage,
    SubscriptionInvoice, DeferredRevenue, DeferredRevenueSchedule,
    MilestoneRevenue
)
from .serializers import (
    SubscriptionPlanSerializer, UsageTierSerializer, SubscriptionSerializer,
    SubscriptionUsageSerializer, SubscriptionInvoiceSerializer,
    DeferredRevenueSerializer, DeferredRevenueScheduleSerializer,
    MilestoneRevenueSerializer
)
from api.permissions import IsOrganizationMember


class BaseBillingViewSet(viewsets.ModelViewSet):
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


class SubscriptionPlanViewSet(BaseBillingViewSet):
    queryset = SubscriptionPlan.objects.prefetch_related('usage_tiers')
    serializer_class = SubscriptionPlanSerializer
    search_fields = ['code', 'name']
    filterset_fields = ['plan_type', 'billing_frequency_unit', 'is_active']
    ordering_fields = ['code', 'name', 'base_price', 'created_at']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get currently active subscription plans"""
        now = timezone.now().date()
        active_plans = self.get_queryset().filter(
            is_active=True,
            valid_from__lte=now
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        )
        return Response(SubscriptionPlanSerializer(active_plans, many=True).data)


class UsageTierViewSet(viewsets.ModelViewSet):
    queryset = UsageTier.objects.select_related('plan')
    serializer_class = UsageTierSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filterset_fields = ['plan']
    
    def get_queryset(self):
        return self.queryset.filter(plan__organization=self.request.user.organization)


class SubscriptionViewSet(BaseBillingViewSet):
    queryset = Subscription.objects.select_related('plan')
    serializer_class = SubscriptionSerializer
    search_fields = ['subscription_number', 'customer_id']
    filterset_fields = ['status', 'plan', 'customer_id']
    ordering_fields = ['start_date', 'current_period_end', 'created_at']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active subscriptions"""
        active_subs = self.get_queryset().filter(status='active')
        return Response(SubscriptionSerializer(active_subs, many=True).data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get subscriptions expiring in the next 30 days"""
        from datetime import timedelta
        now = timezone.now().date()
        thirty_days = now + timedelta(days=30)
        
        expiring = self.get_queryset().filter(
            status='active',
            current_period_end__gte=now,
            current_period_end__lte=thirty_days,
            auto_renew=False
        )
        return Response(SubscriptionSerializer(expiring, many=True).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a subscription"""
        subscription = self.get_object()
        reason = request.data.get('reason', '')
        
        if subscription.status == 'cancelled':
            return Response({'error': 'Subscription already cancelled'}, status=400)
        
        subscription.status = 'cancelled'
        subscription.cancellation_date = timezone.now().date()
        subscription.cancellation_reason = reason
        subscription.updated_by = request.user.id
        subscription.save()
        
        return Response(SubscriptionSerializer(subscription).data)
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """Get subscription metrics"""
        subscription = self.get_object()
        
        # Get total usage
        total_usage = SubscriptionUsage.objects.filter(
            organization=request.user.organization,
            subscription=subscription
        ).aggregate(
            total_quantity=Sum('quantity_used'),
            total_overage=Sum('overage_charge')
        )
        
        # Get total invoiced
        total_invoiced = SubscriptionInvoice.objects.filter(
            organization=request.user.organization,
            subscription=subscription
        ).aggregate(
            total=Sum('total_amount'),
            paid=Sum('total_amount', filter=Q(status='paid'))
        )
        
        return Response({
            'subscription_number': subscription.subscription_number,
            'lifetime_value': total_invoiced['total'] or 0,
            'paid_amount': total_invoiced['paid'] or 0,
            'outstanding_amount': (total_invoiced['total'] or 0) - (total_invoiced['paid'] or 0),
            'total_usage': total_usage['total_quantity'] or 0,
            'total_overage_charges': total_usage['total_overage'] or 0,
            'renewal_count': subscription.renewal_count,
            'months_active': subscription.renewal_count * (subscription.contract_term_months or 1)
        })


class SubscriptionUsageViewSet(BaseBillingViewSet):
    queryset = SubscriptionUsage.objects.select_related('subscription')
    serializer_class = SubscriptionUsageSerializer
    filterset_fields = ['subscription', 'is_billed', 'usage_metric']
    ordering_fields = ['period_start', 'quantity_used', 'overage_charge']
    
    @action(detail=False, methods=['get'])
    def unbilled(self, request):
        """Get unbilled usage"""
        unbilled = self.get_queryset().filter(is_billed=False)
        return Response(SubscriptionUsageSerializer(unbilled, many=True).data)


class SubscriptionInvoiceViewSet(BaseBillingViewSet):
    queryset = SubscriptionInvoice.objects.select_related('subscription')
    serializer_class = SubscriptionInvoiceSerializer
    search_fields = ['invoice_number']
    filterset_fields = ['subscription', 'status']
    ordering_fields = ['invoice_date', 'due_date', 'total_amount']
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue invoices"""
        now = timezone.now().date()
        overdue = self.get_queryset().filter(
            status__in=['draft', 'sent'],
            due_date__lt=now
        )
        return Response(SubscriptionInvoiceSerializer(overdue, many=True).data)
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """Record payment for an invoice"""
        invoice = self.get_object()
        payment_date = request.data.get('payment_date', timezone.now().date())
        payment_method = request.data.get('payment_method', '')
        
        if invoice.status == 'paid':
            return Response({'error': 'Invoice already paid'}, status=400)
        
        invoice.status = 'paid'
        invoice.payment_date = payment_date
        invoice.payment_method = payment_method
        invoice.updated_by = request.user.id
        invoice.save()
        
        return Response(SubscriptionInvoiceSerializer(invoice).data)


class DeferredRevenueViewSet(BaseBillingViewSet):
    queryset = DeferredRevenue.objects.select_related('subscription').prefetch_related('schedule')
    serializer_class = DeferredRevenueSerializer
    search_fields = ['invoice_number']
    filterset_fields = ['subscription', 'is_fully_recognized', 'recognition_method']
    ordering_fields = ['recognition_start_date', 'deferred_amount']
    
    @action(detail=False, methods=['get'])
    def pending_recognition(self, request):
        """Get deferred revenue pending recognition"""
        pending = self.get_queryset().filter(is_fully_recognized=False)
        
        # Calculate total deferred vs recognized
        totals = pending.aggregate(
            total_deferred=Sum('deferred_amount'),
            total_recognized=Sum('recognized_amount')
        )
        
        return Response({
            'pending_count': pending.count(),
            'total_deferred': totals['total_deferred'] or 0,
            'total_recognized': totals['total_recognized'] or 0,
            'remaining_balance': (totals['total_deferred'] or 0) - (totals['total_recognized'] or 0),
            'records': DeferredRevenueSerializer(pending, many=True).data
        })


class DeferredRevenueScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to deferred revenue schedule"""
    queryset = DeferredRevenueSchedule.objects.select_related('deferred_revenue')
    serializer_class = DeferredRevenueScheduleSerializer
    permission_classes = [IsAuthenticated, IsOrganizationMember]
    filterset_fields = ['is_recognized']
    ordering_fields = ['recognition_date']
    
    def get_queryset(self):
        return self.queryset.filter(
            deferred_revenue__organization=self.request.user.organization
        )


class MilestoneRevenueViewSet(BaseBillingViewSet):
    queryset = MilestoneRevenue.objects.select_related('deferred_revenue')
    serializer_class = MilestoneRevenueSerializer
    search_fields = ['milestone_number', 'description', 'deliverable']
    filterset_fields = ['deferred_revenue', 'status']
    ordering_fields = ['due_date', 'milestone_value']
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending milestones"""
        pending = self.get_queryset().filter(status='pending')
        return Response(MilestoneRevenueSerializer(pending, many=True).data)
    
    @action(detail=True, methods=['post'])
    def achieve(self, request, pk=None):
        """Mark milestone as completed"""
        milestone = self.get_object()
        
        if milestone.status in ['completed', 'invoiced', 'recognized']:
            return Response({'error': 'Milestone already completed'}, status=400)
        
        milestone.status = 'completed'
        milestone.completion_date = timezone.now().date()
        milestone.approved_by = request.user.id
        milestone.approved_date = timezone.now()
        milestone.save()
        
        return Response(MilestoneRevenueSerializer(milestone).data)
