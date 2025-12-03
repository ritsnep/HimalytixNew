# dashboard/utils/vertical_metrics.py
"""
Vertical-Specific Metrics Calculators

Provides KPI calculations for each industry vertical:
- Distributors: DIFOT, Perfect Order Rate, Inventory Turnover
- Retailers: GMROI, Sell-Through Rate, Stock-to-Sales Ratio
- Manufacturers: OEE, Yield Rate, Production Variance
- SaaS: ARR, MRR, Churn Rate, Customer Lifetime Value
"""
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from django.db.models import Sum, Count, Avg, Q, F, DecimalField
from django.db.models.functions import Coalesce, TruncMonth, TruncDate
from django.utils import timezone


class DistributorMetrics:
    """
    Metrics for Mid-Sized Distributors
    
    Key Performance Indicators:
    - DIFOT (Delivery In Full On Time)
    - Perfect Order Rate
    - Inventory Turnover
    - Order Fill Rate
    - Days Sales Outstanding (DSO)
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_difot(
        self,
        start_date: date,
        end_date: date,
        warehouse_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate DIFOT (Delivery In Full On Time)
        
        DIFOT % = (Orders delivered in full and on time / Total orders) × 100
        
        Returns:
            {
                'difot_percentage': 95.5,
                'total_orders': 1000,
                'on_time_in_full': 955,
                'late_deliveries': 30,
                'partial_deliveries': 15
            }
        """
        from inventory.models import Shipment
        
        shipments = Shipment.objects.filter(
            organization=self.organization,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='delivered'
        )
        
        if warehouse_id:
            shipments = shipments.filter(ship_from_warehouse_id=warehouse_id)
        
        total_orders = shipments.count()
        
        if total_orders == 0:
            return {
                'difot_percentage': 0,
                'total_orders': 0,
                'on_time_in_full': 0,
                'late_deliveries': 0,
                'partial_deliveries': 0
            }
        
        # Orders delivered on time (actual <= estimated)
        on_time = shipments.filter(
            actual_delivery__lte=F('estimated_delivery')
        ).count()
        
        # Orders delivered late
        late = total_orders - on_time
        
        # TODO: Check "in full" criteria (would need order line comparison)
        # For now, assume all delivered orders were in full
        on_time_in_full = on_time
        
        difot = (on_time_in_full / total_orders) * 100
        
        return {
            'difot_percentage': round(difot, 2),
            'total_orders': total_orders,
            'on_time_in_full': on_time_in_full,
            'late_deliveries': late,
            'partial_deliveries': 0  # TODO: Calculate from order lines
        }
    
    def calculate_inventory_turnover(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate Inventory Turnover Ratio
        
        Inventory Turnover = Cost of Goods Sold / Average Inventory Value
        
        Returns:
            {
                'turnover_ratio': 8.5,
                'cogs': 1000000,
                'average_inventory_value': 117647,
                'days_inventory': 42.9
            }
        """
        from inventory.models import StockLedger, InventoryItem
        
        # Calculate COGS from stock ledger (outbound transactions)
        cogs = StockLedger.objects.filter(
            organization=self.organization,
            txn_date__gte=start_date,
            txn_date__lte=end_date,
            txn_type__in=['sale', 'issue', 'transfer_out']
        ).aggregate(
            total=Coalesce(Sum(F('quantity') * F('cost_per_unit')), Decimal('0.00'))
        )['total']
        
        # Calculate average inventory value
        # Get inventory value at start and end, then average
        start_value = self._get_inventory_value_at_date(start_date)
        end_value = self._get_inventory_value_at_date(end_date)
        avg_inventory = (start_value + end_value) / 2
        
        if avg_inventory == 0:
            turnover_ratio = 0
            days_inventory = 0
        else:
            turnover_ratio = cogs / avg_inventory
            # Days inventory = 365 / turnover ratio
            days_inventory = 365 / turnover_ratio if turnover_ratio > 0 else 0
        
        return {
            'turnover_ratio': round(float(turnover_ratio), 2),
            'cogs': float(cogs),
            'average_inventory_value': float(avg_inventory),
            'days_inventory': round(float(days_inventory), 1)
        }
    
    def calculate_order_fill_rate(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate Order Fill Rate
        
        Fill Rate % = (Lines shipped complete / Total order lines) × 100
        """
        from inventory.models import PickList, PickListLine
        
        pick_lists = PickList.objects.filter(
            organization=self.organization,
            pick_date__gte=start_date,
            pick_date__lte=end_date
        )
        
        total_lines = PickListLine.objects.filter(
            pick_list__in=pick_lists
        ).count()
        
        if total_lines == 0:
            return {
                'fill_rate_percentage': 0,
                'total_lines': 0,
                'filled_lines': 0
            }
        
        # Lines where quantity_picked >= quantity
        filled_lines = PickListLine.objects.filter(
            pick_list__in=pick_lists,
            quantity_picked__gte=F('quantity')
        ).count()
        
        fill_rate = (filled_lines / total_lines) * 100
        
        return {
            'fill_rate_percentage': round(fill_rate, 2),
            'total_lines': total_lines,
            'filled_lines': filled_lines
        }
    
    def _get_inventory_value_at_date(self, target_date: date) -> Decimal:
        """Get total inventory value at a specific date"""
        from inventory.models import InventoryItem
        
        # This is simplified - production would need point-in-time snapshot
        items = InventoryItem.objects.filter(
            organization=self.organization
        ).select_related('product')
        
        total_value = sum(
            item.quantity_on_hand * (item.product.cost_price or Decimal('0.00'))
            for item in items
        )
        
        return total_value


class RetailerMetrics:
    """
    Metrics for Multi-Warehouse Retailers
    
    Key Performance Indicators:
    - GMROI (Gross Margin Return on Investment)
    - Sell-Through Rate
    - Stock-to-Sales Ratio
    - Inventory Turnover by Category
    - Markdown %
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_gmroi(
        self,
        start_date: date,
        end_date: date,
        category_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate GMROI (Gross Margin Return on Investment)
        
        GMROI = Gross Margin / Average Inventory Cost
        
        Returns:
            {
                'gmroi': 3.5,
                'gross_margin': 350000,
                'average_inventory_cost': 100000
            }
        """
        from inventory.models import StockLedger, InventoryItem, Product
        
        # Get sales transactions
        sales = StockLedger.objects.filter(
            organization=self.organization,
            txn_date__gte=start_date,
            txn_date__lte=end_date,
            txn_type='sale'
        ).select_related('product')
        
        if category_id:
            sales = sales.filter(product__category_id=category_id)
        
        # Calculate gross margin (sales revenue - cost)
        gross_margin = Decimal('0.00')
        for sale in sales:
            revenue = sale.quantity * (sale.product.sale_price or Decimal('0.00'))
            cost = sale.quantity * sale.cost_per_unit
            gross_margin += (revenue - cost)
        
        # Get average inventory cost
        items = InventoryItem.objects.filter(
            organization=self.organization
        ).select_related('product')
        
        if category_id:
            items = items.filter(product__category_id=category_id)
        
        avg_inventory_cost = sum(
            item.quantity_on_hand * (item.product.cost_price or Decimal('0.00'))
            for item in items
        )
        
        if avg_inventory_cost == 0:
            gmroi = 0
        else:
            gmroi = gross_margin / avg_inventory_cost
        
        return {
            'gmroi': round(float(gmroi), 2),
            'gross_margin': float(gross_margin),
            'average_inventory_cost': float(avg_inventory_cost)
        }
    
    def calculate_sell_through_rate(
        self,
        start_date: date,
        end_date: date,
        category_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate Sell-Through Rate
        
        Sell-Through % = (Units Sold / Units Received) × 100
        """
        from inventory.models import StockLedger
        
        # Units sold
        sold = StockLedger.objects.filter(
            organization=self.organization,
            txn_date__gte=start_date,
            txn_date__lte=end_date,
            txn_type='sale'
        )
        
        if category_id:
            sold = sold.filter(product__category_id=category_id)
        
        units_sold = sold.aggregate(
            total=Coalesce(Sum('quantity'), Decimal('0.00'))
        )['total']
        
        # Units received
        received = StockLedger.objects.filter(
            organization=self.organization,
            txn_date__gte=start_date,
            txn_date__lte=end_date,
            txn_type__in=['purchase', 'receipt', 'transfer_in']
        )
        
        if category_id:
            received = received.filter(product__category_id=category_id)
        
        units_received = received.aggregate(
            total=Coalesce(Sum('quantity'), Decimal('0.00'))
        )['total']
        
        if units_received == 0:
            sell_through = 0
        else:
            sell_through = (units_sold / units_received) * 100
        
        return {
            'sell_through_percentage': round(float(sell_through), 2),
            'units_sold': float(units_sold),
            'units_received': float(units_received)
        }
    
    def get_top_selling_products(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> List[Dict]:
        """Get top selling products by revenue"""
        from inventory.models import StockLedger
        
        sales = StockLedger.objects.filter(
            organization=self.organization,
            txn_date__gte=start_date,
            txn_date__lte=end_date,
            txn_type='sale'
        ).select_related('product').values(
            'product__code',
            'product__name'
        ).annotate(
            units_sold=Sum('quantity'),
            revenue=Sum(F('quantity') * F('product__sale_price'), output_field=DecimalField())
        ).order_by('-revenue')[:limit]
        
        return [
            {
                'product_code': s['product__code'],
                'product_name': s['product__name'],
                'units_sold': float(s['units_sold']),
                'revenue': float(s['revenue'] or 0)
            }
            for s in sales
        ]


class ManufacturerMetrics:
    """
    Metrics for Contract Manufacturers
    
    Key Performance Indicators:
    - OEE (Overall Equipment Effectiveness)
    - Yield Rate
    - Production Variance
    - First Pass Yield
    - Scrap Rate
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_oee(
        self,
        start_date: date,
        end_date: date,
        work_center_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate OEE (Overall Equipment Effectiveness)
        
        OEE = Availability × Performance × Quality
        
        Returns:
            {
                'oee_percentage': 75.0,
                'availability': 90.0,
                'performance': 95.0,
                'quality': 88.0
            }
        """
        from enterprise.models import WorkOrder, YieldTracking
        
        work_orders = WorkOrder.objects.filter(
            organization=self.organization,
            start_date__gte=start_date,
            start_date__lte=end_date,
            status__in=['in_progress', 'completed']
        )
        
        if work_center_id:
            work_orders = work_orders.filter(work_center_id=work_center_id)
        
        if not work_orders.exists():
            return {
                'oee_percentage': 0,
                'availability': 0,
                'performance': 0,
                'quality': 0
            }
        
        # Calculate Availability
        # Availability = Operating Time / Planned Production Time
        total_planned_hours = Decimal('0.00')
        total_operating_hours = Decimal('0.00')
        
        for wo in work_orders:
            if wo.end_date and wo.start_date:
                planned = (wo.end_date - wo.start_date).total_seconds() / 3600
                total_planned_hours += Decimal(str(planned))
                # Assume 95% of planned time is actual operating time (simplified)
                total_operating_hours += Decimal(str(planned)) * Decimal('0.95')
        
        availability = (total_operating_hours / total_planned_hours * 100) if total_planned_hours > 0 else 0
        
        # Calculate Performance
        # Performance = (Actual Output / Ideal Output) × 100
        # Simplified: assume 95% performance
        performance = Decimal('95.00')
        
        # Calculate Quality from yield tracking
        yields = YieldTracking.objects.filter(
            work_order__in=work_orders
        )
        
        if yields.exists():
            avg_yield = yields.aggregate(
                avg=Avg('yield_percentage')
            )['avg'] or Decimal('0.00')
            quality = avg_yield
        else:
            quality = Decimal('88.00')  # Default
        
        # Calculate OEE
        oee = (availability * performance * quality) / 10000  # Divide by 10000 since all are percentages
        
        return {
            'oee_percentage': round(float(oee), 2),
            'availability': round(float(availability), 2),
            'performance': round(float(performance), 2),
            'quality': round(float(quality), 2)
        }
    
    def calculate_yield_rate(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate overall yield rate
        
        Yield % = (Good Units / Total Units Started) × 100
        """
        from enterprise.models import YieldTracking
        
        yields = YieldTracking.objects.filter(
            organization=self.organization,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        if not yields.exists():
            return {
                'yield_percentage': 0,
                'good_units': 0,
                'total_units': 0,
                'defective_units': 0
            }
        
        total_good = yields.aggregate(total=Sum('good_quantity'))['total'] or Decimal('0.00')
        total_defective = yields.aggregate(total=Sum('defective_quantity'))['total'] or Decimal('0.00')
        total_units = total_good + total_defective
        
        yield_pct = (total_good / total_units * 100) if total_units > 0 else 0
        
        return {
            'yield_percentage': round(float(yield_pct), 2),
            'good_units': float(total_good),
            'total_units': float(total_units),
            'defective_units': float(total_defective)
        }
    
    def calculate_production_variance(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate production cost variance
        
        Variance = Standard Cost - Actual Cost
        """
        from enterprise.models import WorkOrderCosting
        
        costings = WorkOrderCosting.objects.filter(
            organization=self.organization,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        total_standard = costings.aggregate(
            total=Coalesce(Sum('standard_cost'), Decimal('0.00'))
        )['total']
        
        total_actual = costings.aggregate(
            total=Coalesce(Sum('actual_cost'), Decimal('0.00'))
        )['total']
        
        variance = total_standard - total_actual
        variance_pct = (variance / total_standard * 100) if total_standard > 0 else 0
        
        return {
            'cost_variance': float(variance),
            'variance_percentage': round(float(variance_pct), 2),
            'standard_cost': float(total_standard),
            'actual_cost': float(total_actual),
            'favorable': variance > 0
        }


class SaaSMetrics:
    """
    Metrics for SaaS Service Companies
    
    Key Performance Indicators:
    - ARR (Annual Recurring Revenue)
    - MRR (Monthly Recurring Revenue)
    - Churn Rate
    - Customer Lifetime Value (LTV)
    - Customer Acquisition Cost (CAC)
    - LTV:CAC Ratio
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_mrr_arr(
        self,
        as_of_date: Optional[date] = None
    ) -> Dict:
        """
        Calculate MRR and ARR
        
        MRR = Sum of all monthly recurring subscription revenue
        ARR = MRR × 12
        """
        from billing.models.subscription import Subscription
        
        if not as_of_date:
            as_of_date = date.today()
        
        # Get active subscriptions
        active_subs = Subscription.objects.filter(
            organization=self.organization,
            status='active',
            start_date__lte=as_of_date
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=as_of_date)
        )
        
        # Calculate MRR
        mrr = Decimal('0.00')
        for sub in active_subs:
            # Normalize to monthly
            if sub.billing_frequency_unit == 'month':
                monthly = sub.effective_price / sub.billing_frequency
            elif sub.billing_frequency_unit == 'year':
                monthly = sub.effective_price / 12
            else:
                monthly = sub.effective_price  # Assume monthly
            
            mrr += monthly
        
        arr = mrr * 12
        
        # Get subscription count
        total_subs = active_subs.count()
        arpu = mrr / total_subs if total_subs > 0 else 0  # Average Revenue Per User
        
        return {
            'mrr': float(mrr),
            'arr': float(arr),
            'total_subscriptions': total_subs,
            'arpu': round(float(arpu), 2)
        }
    
    def calculate_churn_rate(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate customer churn rate
        
        Churn Rate = (Customers Lost / Customers at Start) × 100
        """
        from billing.models.subscription import Subscription
        
        # Customers at start of period
        start_customers = Subscription.objects.filter(
            organization=self.organization,
            status='active',
            start_date__lt=start_date
        ).values('customer_id').distinct().count()
        
        # Customers lost (cancelled) during period
        churned = Subscription.objects.filter(
            organization=self.organization,
            status='cancelled',
            cancellation_date__gte=start_date,
            cancellation_date__lte=end_date
        ).values('customer_id').distinct().count()
        
        # Customer churn rate
        churn_rate = (churned / start_customers * 100) if start_customers > 0 else 0
        
        # Revenue churn
        churned_subs = Subscription.objects.filter(
            organization=self.organization,
            status='cancelled',
            cancellation_date__gte=start_date,
            cancellation_date__lte=end_date
        )
        
        churned_mrr = sum(
            sub.effective_price / (12 if sub.billing_frequency_unit == 'year' else sub.billing_frequency)
            for sub in churned_subs
        )
        
        return {
            'customer_churn_rate': round(float(churn_rate), 2),
            'customers_lost': churned,
            'customers_at_start': start_customers,
            'churned_mrr': float(churned_mrr)
        }
    
    def calculate_ltv_cac(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate LTV (Lifetime Value) and CAC (Customer Acquisition Cost)
        
        LTV = Average Revenue Per User × Customer Lifetime
        CAC = Total Sales & Marketing Costs / New Customers Acquired
        """
        from billing.models.subscription import Subscription, SubscriptionInvoice
        
        # Calculate ARPU
        active_subs = Subscription.objects.filter(
            organization=self.organization,
            status='active'
        )
        
        total_revenue = active_subs.aggregate(
            total=Sum('effective_price')
        )['total'] or Decimal('0.00')
        
        customer_count = active_subs.values('customer_id').distinct().count()
        arpu = total_revenue / customer_count if customer_count > 0 else 0
        
        # Estimate customer lifetime (inverse of churn rate)
        churn_data = self.calculate_churn_rate(start_date, end_date)
        if churn_data['customer_churn_rate'] > 0:
            customer_lifetime_months = 100 / churn_data['customer_churn_rate']
        else:
            customer_lifetime_months = 24  # Default 2 years
        
        # Calculate LTV (monthly ARPU × lifetime)
        ltv = arpu * Decimal(str(customer_lifetime_months))
        
        # CAC calculation (simplified - would need actual marketing costs)
        # For now, use a typical SaaS CAC estimate
        cac = arpu * 3  # Assume CAC is ~3x monthly revenue
        
        ltv_cac_ratio = ltv / cac if cac > 0 else 0
        
        return {
            'ltv': round(float(ltv), 2),
            'cac': round(float(cac), 2),
            'ltv_cac_ratio': round(float(ltv_cac_ratio), 2),
            'arpu': round(float(arpu), 2),
            'customer_lifetime_months': round(float(customer_lifetime_months), 1)
        }
    
    def get_subscription_cohort_analysis(
        self,
        cohort_month: date
    ) -> Dict:
        """
        Analyze subscription retention by cohort
        
        Returns retention rates for customers acquired in a specific month
        """
        from billing.models.subscription import Subscription
        
        cohort_start = cohort_month.replace(day=1)
        cohort_end = (cohort_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Get customers who started in this cohort
        cohort_customers = Subscription.objects.filter(
            organization=self.organization,
            start_date__gte=cohort_start,
            start_date__lte=cohort_end
        ).values_list('customer_id', flat=True).distinct()
        
        cohort_size = len(cohort_customers)
        
        if cohort_size == 0:
            return {
                'cohort_month': cohort_month.isoformat(),
                'cohort_size': 0,
                'retention_by_month': {}
            }
        
        # Calculate retention for each subsequent month
        retention = {}
        current_month = cohort_start
        
        for month_offset in range(6):  # 6 months retention
            check_date = current_month + timedelta(days=30 * month_offset)
            
            # Count how many are still active
            still_active = Subscription.objects.filter(
                organization=self.organization,
                customer_id__in=cohort_customers,
                status='active',
                start_date__lte=check_date
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=check_date)
            ).values('customer_id').distinct().count()
            
            retention_rate = (still_active / cohort_size * 100)
            retention[f"month_{month_offset}"] = round(float(retention_rate), 2)
        
        return {
            'cohort_month': cohort_month.isoformat(),
            'cohort_size': cohort_size,
            'retention_by_month': retention
        }


class ServiceMetrics:
    """
    Metrics for Service Management
    
    Key Performance Indicators:
    - SLA Compliance Rate
    - Mean Time to Resolution (MTTR)
    - First Contact Resolution Rate
    - Service Margin %
    - Warranty Claim Rate
    """
    
    def __init__(self, organization):
        self.organization = organization
    
    def calculate_sla_compliance(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """Calculate SLA compliance rate"""
        from service_management.models import ServiceTicket
        
        tickets = ServiceTicket.objects.filter(
            organization=self.organization,
            reported_date__gte=start_date,
            reported_date__lte=end_date,
            status__in=['resolved', 'closed']
        )
        
        total_tickets = tickets.count()
        
        if total_tickets == 0:
            return {
                'sla_compliance_rate': 0,
                'total_tickets': 0,
                'within_sla': 0,
                'breached_sla': 0
            }
        
        # Tickets resolved within SLA
        within_sla = 0
        for ticket in tickets:
            if ticket.resolved_date and ticket.sla_resolution_due:
                if ticket.resolved_date <= ticket.sla_resolution_due:
                    within_sla += 1
        
        compliance_rate = (within_sla / total_tickets) * 100
        
        return {
            'sla_compliance_rate': round(compliance_rate, 2),
            'total_tickets': total_tickets,
            'within_sla': within_sla,
            'breached_sla': total_tickets - within_sla
        }
    
    def calculate_mttr(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """Calculate Mean Time to Resolution"""
        from service_management.models import ServiceTicket
        
        resolved = ServiceTicket.objects.filter(
            organization=self.organization,
            reported_date__gte=start_date,
            reported_date__lte=end_date,
            status__in=['resolved', 'closed'],
            resolved_date__isnull=False
        )
        
        if not resolved.exists():
            return {
                'mttr_hours': 0,
                'total_resolved': 0
            }
        
        total_resolution_time = sum(
            (ticket.resolved_date - ticket.reported_date).total_seconds() / 3600
            for ticket in resolved
        )
        
        mttr = total_resolution_time / resolved.count()
        
        return {
            'mttr_hours': round(mttr, 2),
            'total_resolved': resolved.count()
        }
