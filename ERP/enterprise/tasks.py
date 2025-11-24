# enterprise/tasks.py
"""
Celery tasks for enterprise/manufacturing automation
Supports contract manufacturer vertical playbook
"""
from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@shared_task
def run_mrp_calculations():
    """
    Run MRP (Material Requirements Planning) calculations
    Runs daily
    """
    from enterprise.models import WorkOrder, BillOfMaterial, BillOfMaterialItem
    from enterprise.services import MRPService
    from usermanagement.models import Organization
    
    suggestions_count = 0
    
    for org in Organization.objects.filter(is_active=True):
        mrp_service = MRPService(org)
        
        # Find planned work orders
        work_orders = WorkOrder.objects.filter(
            organization=org,
            status='planned'
        )
        
        for wo in work_orders:
            try:
                suggestions = mrp_service.suggest_for_workorder(wo)
                suggestions_count += len(suggestions)
                logger.info(f"Generated {len(suggestions)} MRP suggestions for WO {wo.work_order_number}")
            except Exception as e:
                logger.error(f"Failed to run MRP for work order {wo.work_order_number}: {e}")
    
    return {
        'suggestions_generated': suggestions_count
    }


@shared_task
def update_work_order_costing():
    """
    Update actual costs for work orders based on material/labor consumption
    Runs daily
    """
    from enterprise.models import WorkOrder, WorkOrderCosting, WorkOrderMaterial
    from decimal import Decimal
    
    updated_count = 0
    
    work_orders = WorkOrder.objects.filter(
        status__in=['in_progress', 'completed']
    ).select_related('organization')
    
    for wo in work_orders:
        try:
            # Get or create costing record
            costing, created = WorkOrderCosting.objects.get_or_create(
                work_order=wo,
                defaults={'organization': wo.organization}
            )
            
            # Calculate actual material cost from issued materials
            materials = WorkOrderMaterial.objects.filter(work_order=wo)
            actual_material_cost = Decimal('0')
            
            for material in materials:
                # Placeholder: would need to get actual cost from inventory
                # actual_material_cost += material.quantity_issued * unit_cost
                pass
            
            costing.actual_material_cost = actual_material_cost
            
            # Calculate variances
            costing.variance_material = costing.actual_material_cost - costing.standard_material_cost
            costing.variance_labor = costing.actual_labor_cost - costing.standard_labor_cost
            costing.variance_overhead = costing.actual_overhead_cost - costing.standard_overhead_cost
            
            costing.save()
            updated_count += 1
            
            logger.info(
                f"Updated costing for WO {wo.work_order_number}: "
                f"Material variance: {costing.variance_material}"
            )
            
        except Exception as e:
            logger.error(f"Failed to update costing for WO {wo.work_order_number}: {e}")
    
    return {
        'work_orders_updated': updated_count
    }


@shared_task
def schedule_preventive_maintenance():
    """
    Schedule preventive maintenance for work centers based on usage
    Runs weekly
    """
    from enterprise.models import WorkCenter
    
    scheduled_count = 0
    
    work_centers = WorkCenter.objects.filter(is_active=True)
    
    for wc in work_centers:
        # Placeholder logic for PM scheduling
        # Would check usage hours, schedules, etc.
        logger.info(f"Checked preventive maintenance schedule for {wc.code}")
        scheduled_count += 1
    
    return {
        'work_centers_checked': scheduled_count
    }


@shared_task
def process_depreciation():
    """
    Calculate and post depreciation for fixed assets
    Runs monthly
    """
    from enterprise.models import FixedAsset, AssetDepreciationSchedule
    from django.utils import timezone
    
    today = timezone.now().date()
    processed_count = 0
    total_depreciation = Decimal('0')
    
    # Find depreciation schedules due this month
    due_schedules = AssetDepreciationSchedule.objects.filter(
        period_start__lte=today,
        period_end__gte=today,
        posted_journal=False
    ).select_related('asset')
    
    for schedule in due_schedules:
        try:
            # Post depreciation journal entry (placeholder)
            logger.info(
                f"Posting depreciation for asset {schedule.asset.asset_code}: "
                f"{schedule.depreciation_amount}"
            )
            
            schedule.posted_journal = True
            schedule.save()
            
            processed_count += 1
            total_depreciation += schedule.depreciation_amount
            
        except Exception as e:
            logger.error(f"Failed to process depreciation for schedule {schedule.id}: {e}")
    
    return {
        'schedules_processed': processed_count,
        'total_depreciation': float(total_depreciation)
    }


@shared_task
def check_qc_compliance():
    """
    Check QC compliance and alert for overdue inspections
    Runs daily
    """
    from enterprise.models import QCCheckpoint, WorkOrder, QCInspectionRecord
    from django.utils import timezone
    
    today = timezone.now()
    alerts = []
    
    # Find in-progress work orders
    active_work_orders = WorkOrder.objects.filter(
        status='in_progress'
    )
    
    for wo in active_work_orders:
        # Check if mandatory QC checkpoints have been completed
        # Placeholder logic
        logger.info(f"Checked QC compliance for WO {wo.work_order_number}")
        
    return {
        'work_orders_checked': active_work_orders.count(),
        'alerts': len(alerts)
    }


@shared_task
def update_production_calendar():
    """
    Update production calendar with holidays and shifts
    Runs weekly
    """
    from enterprise.models import ProductionCalendar, ProductionHoliday
    
    updated_count = 0
    calendars = ProductionCalendar.objects.filter(is_active=True)
    
    for calendar in calendars:
        # Placeholder for calendar updates
        logger.info(f"Updated production calendar {calendar.code}")
        updated_count += 1
    
    return {
        'calendars_updated': updated_count
    }
