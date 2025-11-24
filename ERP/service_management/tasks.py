# service_management/tasks.py
"""
Celery tasks for service management automation
Supports SaaS vertical playbook
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_device_warranty_expiration():
    """
    Check for devices with warranties expiring soon and send alerts
    Runs daily
    """
    from .models import DeviceLifecycle
    
    today = timezone.now().date()
    warning_days = [7, 30, 60, 90]  # Alert at these intervals before expiration
    alerts = []
    
    for days in warning_days:
        target_date = today + timedelta(days=days)
        
        devices = DeviceLifecycle.objects.filter(
            state__in=['deployed', 'maintenance'],
            warranty_end_date=target_date
        )
        
        for device in devices:
            alerts.append({
                'device_serial': device.serial_number,
                'device_model': device.device_model.model_number,
                'customer_id': device.customer_id,
                'warranty_expires': str(device.warranty_end_date),
                'days_remaining': days
            })
            
            logger.warning(
                f"Warranty expiring for device {device.serial_number} "
                f"in {days} days"
            )
    
    return {
        'total_alerts': len(alerts),
        'alerts': alerts
    }


@shared_task
def check_service_contract_renewals():
    """
    Check for service contracts expiring soon and send renewal notifications
    Runs daily
    """
    from .models import ServiceContract
    
    today = timezone.now().date()
    renewal_window_days = [7, 14, 30, 60]
    renewals_needed = []
    
    for days in renewal_window_days:
        target_date = today + timedelta(days=days)
        
        contracts = ServiceContract.objects.filter(
            status='active',
            end_date=target_date,
            auto_renew=False
        )
        
        for contract in contracts:
            renewals_needed.append({
                'contract_number': contract.contract_number,
                'customer_id': contract.customer_id,
                'contract_type': contract.contract_type,
                'end_date': str(contract.end_date),
                'days_remaining': days,
                'annual_value': float(contract.annual_value)
            })
            
            logger.info(
                f"Service contract {contract.contract_number} expires in {days} days"
            )
    
    return {
        'contracts_requiring_renewal': len(renewals_needed),
        'renewals': renewals_needed
    }


@shared_task
def auto_renew_service_contracts():
    """
    Automatically renew service contracts with auto_renew enabled
    Runs daily
    """
    from .models import ServiceContract
    from django.db import transaction
    
    today = timezone.now().date()
    renewed_count = 0
    failed_count = 0
    
    contracts_to_renew = ServiceContract.objects.filter(
        status='active',
        end_date=today,
        auto_renew=True
    )
    
    for contract in contracts_to_renew:
        try:
            with transaction.atomic():
                # Extend contract by one year
                old_end_date = contract.end_date
                contract.start_date = old_end_date + timedelta(days=1)
                contract.end_date = contract.start_date + timedelta(days=365)
                contract.renewal_date = contract.end_date
                contract.save()
                
                renewed_count += 1
                logger.info(
                    f"Auto-renewed service contract {contract.contract_number} "
                    f"from {old_end_date} to {contract.end_date}"
                )
                
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to auto-renew contract {contract.contract_number}: {e}")
    
    return {
        'renewed': renewed_count,
        'failed': failed_count
    }


@shared_task
def check_sla_breaches():
    """
    Check for service tickets breaching SLA and escalate
    Runs hourly
    """
    from .models import ServiceTicket, ServiceContract
    from django.utils import timezone
    
    now = timezone.now()
    breaches = []
    
    # Find open tickets without first response
    open_tickets = ServiceTicket.objects.filter(
        status__in=['open', 'in_progress'],
        first_response_date__isnull=True
    ).select_related('service_contract')
    
    for ticket in open_tickets:
        if ticket.service_contract:
            response_time = ticket.service_contract.response_time_hours
            deadline = ticket.created_date + timedelta(hours=response_time)
            
            if now > deadline:
                ticket.sla_breach = True
                ticket.save()
                
                breaches.append({
                    'ticket_number': ticket.ticket_number,
                    'customer_id': ticket.customer_id,
                    'created_date': str(ticket.created_date),
                    'deadline': str(deadline),
                    'hours_overdue': int((now - deadline).total_seconds() / 3600)
                })
                
                logger.warning(f"SLA breach detected for ticket {ticket.ticket_number}")
    
    return {
        'sla_breaches': len(breaches),
        'breached_tickets': breaches
    }


@shared_task
def check_warranty_pool_levels():
    """
    Check warranty pool levels and alert when below minimum
    Runs daily
    """
    from .models import WarrantyPool
    
    low_pools = []
    
    pools = WarrantyPool.objects.filter(is_active=True)
    
    for pool in pools:
        if pool.needs_replenishment:
            low_pools.append({
                'pool_name': pool.pool_name,
                'device_model': pool.device_model.model_number,
                'available': pool.available_quantity,
                'minimum': pool.minimum_quantity,
                'shortage': pool.minimum_quantity - pool.available_quantity
            })
            
            logger.warning(
                f"Low warranty pool: {pool.pool_name} - {pool.device_model.model_number} "
                f"(Available: {pool.available_quantity}, Min: {pool.minimum_quantity})"
            )
    
    return {
        'pools_below_minimum': len(low_pools),
        'low_pools': low_pools
    }


@shared_task
def process_device_telemetry():
    """
    Process IoT/RMM telemetry data and update device status
    Runs every 15 minutes
    """
    from .models import DeviceLifecycle
    
    updated_count = 0
    offline_count = 0
    
    # Find deployed devices
    deployed_devices = DeviceLifecycle.objects.filter(
        state='deployed'
    )
    
    for device in deployed_devices:
        # Placeholder: Would integrate with actual telemetry service
        # Check if device has reported recently
        if device.last_telemetry_received:
            time_since_last = timezone.now() - device.last_telemetry_received
            
            if time_since_last > timedelta(hours=1):
                device.telemetry_status = 'offline'
                offline_count += 1
                logger.warning(f"Device {device.serial_number} appears offline")
            else:
                device.telemetry_status = 'online'
            
            device.save()
            updated_count += 1
    
    return {
        'devices_checked': updated_count,
        'offline_devices': offline_count
    }


@shared_task
def provision_new_devices():
    """
    Automatically provision devices in provisioning state
    Runs every hour
    """
    from .models import DeviceLifecycle, DeviceProvisioningLog
    
    provisioned_count = 0
    failed_count = 0
    
    devices_to_provision = DeviceLifecycle.objects.filter(
        state='provisioning'
    )
    
    for device in devices_to_provision:
        try:
            # Placeholder: Would execute actual provisioning scripts
            logger.info(f"Provisioning device {device.serial_number}")
            
            # Create provisioning log
            log = DeviceProvisioningLog.objects.create(
                device=device,
                provisioned_by=0,  # System user
                status='in_progress'
            )
            
            # Simulate successful provisioning
            log.status = 'success'
            log.completion_date = timezone.now()
            log.save()
            
            # Update device state
            device.state = 'deployed'
            device.save()
            
            provisioned_count += 1
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to provision device {device.serial_number}: {e}")
    
    return {
        'provisioned': provisioned_count,
        'failed': failed_count
    }


@shared_task
def generate_service_metrics():
    """
    Calculate service delivery metrics (uptime, response time, resolution time)
    Runs daily
    """
    from .models import ServiceTicket, ServiceContract
    from django.db.models import Avg, Count
    from decimal import Decimal
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    metrics = []
    
    # Calculate metrics per contract
    contracts = ServiceContract.objects.filter(status='active')
    
    for contract in contracts:
        tickets = ServiceTicket.objects.filter(
            service_contract=contract,
            created_date__date=yesterday
        )
        
        if tickets.exists():
            # Calculate average response time
            responded_tickets = tickets.exclude(first_response_date__isnull=True)
            avg_response_hours = 0
            
            if responded_tickets.exists():
                total_response_time = sum(
                    (t.first_response_date - t.created_date).total_seconds() / 3600
                    for t in responded_tickets
                )
                avg_response_hours = total_response_time / responded_tickets.count()
            
            # Calculate resolution metrics
            resolved_tickets = tickets.filter(status='resolved')
            avg_resolution_hours = 0
            
            if resolved_tickets.exists():
                total_resolution_time = sum(
                    (t.resolution_date - t.created_date).total_seconds() / 3600
                    for t in resolved_tickets if t.resolution_date
                )
                avg_resolution_hours = total_resolution_time / resolved_tickets.count()
            
            # SLA compliance
            sla_breaches = tickets.filter(sla_breach=True).count()
            sla_compliance = ((tickets.count() - sla_breaches) / tickets.count() * 100) if tickets.count() > 0 else 100
            
            metrics.append({
                'contract': contract.contract_number,
                'total_tickets': tickets.count(),
                'avg_response_hours': round(avg_response_hours, 2),
                'avg_resolution_hours': round(avg_resolution_hours, 2),
                'sla_compliance_percent': round(sla_compliance, 2),
                'sla_breaches': sla_breaches
            })
    
    return {
        'contracts_analyzed': len(metrics),
        'metrics': metrics
    }
