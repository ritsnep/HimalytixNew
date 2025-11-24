# billing/tasks.py
"""
Celery tasks for subscription billing automation
Supports SaaS vertical playbook
"""
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_subscription_renewals():
    """
    Process subscription renewals for subscriptions due for billing
    Runs daily
    """
    from billing.models.subscription import Subscription, SubscriptionInvoice
    from billing.models import InvoiceHeader, InvoiceLine
    
    today = timezone.now().date()
    renewed_count = 0
    failed_count = 0
    
    # Find subscriptions due for renewal
    due_subscriptions = Subscription.objects.filter(
        status='active',
        next_billing_date__lte=today
    ).select_related('subscription_plan', 'organization')
    
    for subscription in due_subscriptions:
        try:
            with transaction.atomic():
                # Calculate billing amount
                amount = subscription.effective_price
                
                # Create invoice (simplified - actual implementation would use invoice service)
                # This is a placeholder for the integration
                logger.info(
                    f"Processing renewal for subscription {subscription.subscription_number}: "
                    f"Amount {amount}"
                )
                
                # Update subscription dates
                plan = subscription.subscription_plan
                if plan.billing_cycle == 'monthly':
                    subscription.current_period_start = subscription.current_period_end + timedelta(days=1)
                    subscription.current_period_end = subscription.current_period_start + timedelta(days=30)
                    subscription.next_billing_date = subscription.current_period_end
                elif plan.billing_cycle == 'quarterly':
                    subscription.current_period_start = subscription.current_period_end + timedelta(days=1)
                    subscription.current_period_end = subscription.current_period_start + timedelta(days=90)
                    subscription.next_billing_date = subscription.current_period_end
                elif plan.billing_cycle == 'annual':
                    subscription.current_period_start = subscription.current_period_end + timedelta(days=1)
                    subscription.current_period_end = subscription.current_period_start + timedelta(days=365)
                    subscription.next_billing_date = subscription.current_period_end
                
                subscription.save()
                renewed_count += 1
                
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to renew subscription {subscription.subscription_number}: {e}")
    
    return {
        'renewed': renewed_count,
        'failed': failed_count
    }


@shared_task
def send_renewal_reminders():
    """
    Send renewal reminders for subscriptions expiring soon
    Runs daily
    """
    from billing.models.subscription import Subscription
    
    today = timezone.now().date()
    reminder_dates = [7, 14, 30]  # Days before renewal
    reminders_sent = []
    
    for days in reminder_dates:
        target_date = today + timedelta(days=days)
        
        subscriptions = Subscription.objects.filter(
            status='active',
            next_billing_date=target_date,
            auto_renew=False
        )
        
        for sub in subscriptions:
            # Send reminder notification (placeholder)
            logger.info(
                f"Renewal reminder for subscription {sub.subscription_number} "
                f"({days} days before renewal)"
            )
            reminders_sent.append({
                'subscription': sub.subscription_number,
                'customer_id': sub.customer_id,
                'days_until_renewal': days
            })
    
    return {
        'reminders_sent': len(reminders_sent),
        'details': reminders_sent
    }


@shared_task
def recognize_deferred_revenue():
    """
    Recognize deferred revenue based on schedules (ASC 606 compliance)
    Runs daily
    """
    from billing.models.subscription import DeferredRevenueSchedule
    from accounting.models import Journal, JournalLine, ChartOfAccount
    
    today = timezone.now().date()
    recognized_count = 0
    total_amount = Decimal('0')
    
    # Find schedule lines due for recognition
    due_schedules = DeferredRevenueSchedule.objects.filter(
        recognition_date__lte=today,
        is_recognized=False
    ).select_related('deferred_revenue')
    
    for schedule in due_schedules:
        try:
            with transaction.atomic():
                deferred_rev = schedule.deferred_revenue
                
                # Create journal entry (placeholder - actual implementation would use accounting service)
                logger.info(
                    f"Recognizing deferred revenue: {schedule.recognition_amount} "
                    f"for subscription {deferred_rev.subscription.subscription_number if deferred_rev.subscription else 'N/A'}"
                )
                
                # Mark as recognized
                schedule.is_recognized = True
                schedule.recognized_date = timezone.now()
                schedule.save()
                
                # Update parent deferred revenue
                deferred_rev.recognized_amount += schedule.recognition_amount
                if deferred_rev.recognized_amount >= deferred_rev.deferred_amount:
                    deferred_rev.is_fully_recognized = True
                deferred_rev.save()
                
                recognized_count += 1
                total_amount += schedule.recognition_amount
                
        except Exception as e:
            logger.error(f"Failed to recognize revenue for schedule {schedule.id}: {e}")
    
    return {
        'schedules_recognized': recognized_count,
        'total_amount': float(total_amount)
    }


@shared_task
def calculate_usage_billing():
    """
    Calculate usage-based billing charges for subscriptions
    Runs daily
    """
    from billing.models.subscription import Subscription, SubscriptionUsage, UsageTier
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    calculated_count = 0
    total_charges = Decimal('0')
    
    # Find usage records from yesterday that haven't been billed
    usage_records = SubscriptionUsage.objects.filter(
        usage_date=yesterday,
        is_billed=False
    ).select_related('subscription', 'subscription__subscription_plan')
    
    for usage in usage_records:
        try:
            plan = usage.subscription.subscription_plan
            
            # Find applicable tier
            tiers = UsageTier.objects.filter(
                subscription_plan=plan,
                min_quantity__lte=usage.quantity
            ).order_by('-min_quantity')
            
            if tiers.exists():
                tier = tiers.first()
                
                # Check if quantity exceeds max (if set)
                if tier.max_quantity and usage.quantity > tier.max_quantity:
                    # Base tier amount
                    base_amount = tier.max_quantity * tier.price_per_unit
                    # Overage amount
                    overage_qty = usage.quantity - tier.max_quantity
                    overage_price = tier.overage_price or tier.price_per_unit
                    overage_amount = overage_qty * overage_price
                    total_amount = base_amount + overage_amount
                else:
                    total_amount = usage.quantity * tier.price_per_unit
                
                usage.tier_applied = tier
                usage.calculated_amount = total_amount
                usage.save()
                
                calculated_count += 1
                total_charges += total_amount
                
                logger.info(
                    f"Calculated usage charge: {usage.subscription.subscription_number} - "
                    f"{usage.usage_type}: {usage.quantity} {usage.unit_of_measure} = {total_amount}"
                )
                
        except Exception as e:
            logger.error(f"Failed to calculate usage for record {usage.id}: {e}")
    
    return {
        'records_calculated': calculated_count,
        'total_charges': float(total_charges)
    }


@shared_task
def expire_trial_subscriptions():
    """
    Expire trial subscriptions that have passed their trial period
    Runs daily
    """
    from billing.models.subscription import Subscription
    
    today = timezone.now().date()
    expired_count = 0
    
    trial_subscriptions = Subscription.objects.filter(
        status='trial',
        trial_end_date__lt=today
    )
    
    for subscription in trial_subscriptions:
        # Check if should convert to active or expire
        if subscription.auto_renew:
            subscription.status = 'active'
            logger.info(f"Converted trial subscription to active: {subscription.subscription_number}")
        else:
            subscription.status = 'expired'
            logger.info(f"Expired trial subscription: {subscription.subscription_number}")
        
        subscription.save()
        expired_count += 1
    
    return {
        'subscriptions_processed': expired_count
    }


@shared_task
def generate_arr_metrics():
    """
    Calculate ARR (Annual Recurring Revenue) and MRR metrics
    Runs daily
    """
    from billing.models.subscription import Subscription
    from usermanagement.models import Organization
    from decimal import Decimal
    
    metrics = []
    
    for org in Organization.objects.filter(is_active=True):
        active_subs = Subscription.objects.filter(
            organization=org,
            status='active'
        ).select_related('subscription_plan')
        
        total_mrr = Decimal('0')
        
        for sub in active_subs:
            # Calculate MRR based on billing cycle
            price = sub.effective_price
            
            if sub.subscription_plan.billing_cycle == 'monthly':
                mrr = price
            elif sub.subscription_plan.billing_cycle == 'quarterly':
                mrr = price / 3
            elif sub.subscription_plan.billing_cycle == 'semi_annual':
                mrr = price / 6
            elif sub.subscription_plan.billing_cycle == 'annual':
                mrr = price / 12
            else:
                mrr = Decimal('0')
            
            total_mrr += mrr
        
        total_arr = total_mrr * 12
        
        metrics.append({
            'organization': org.name,
            'active_subscriptions': active_subs.count(),
            'mrr': float(total_mrr),
            'arr': float(total_arr)
        })
        
        logger.info(f"ARR metrics for {org.name}: MRR=${total_mrr}, ARR=${total_arr}")
    
    return {
        'organizations': len(metrics),
        'metrics': metrics
    }
