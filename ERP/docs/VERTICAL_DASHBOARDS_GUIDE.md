# Vertical Dashboards Guide

## Overview

This guide covers the vertical-specific dashboard APIs that provide key performance indicators (KPIs) for different industry verticals. Each vertical has custom metrics tailored to their business needs.

## Table of Contents

1. [Distributor Dashboard](#distributor-dashboard)
2. [Retailer Dashboard](#retailer-dashboard)
3. [Manufacturer Dashboard](#manufacturer-dashboard)
4. [SaaS Dashboard](#saas-dashboard)
5. [Service Dashboard](#service-dashboard)
6. [Unified Dashboard](#unified-dashboard)
7. [Integration Examples](#integration-examples)

---

## Distributor Dashboard

### Overview
The distributor dashboard focuses on logistics, fulfillment, and inventory management KPIs critical for wholesale distribution businesses.

### Key Metrics

#### 1. DIFOT (Delivery In Full On Time)
```
DIFOT % = (Orders delivered in full and on time / Total orders) × 100
```

**Endpoint:** `GET /api/dashboards/distributor/`

**Query Parameters:**
- `start_date` (optional): YYYY-MM-DD format, defaults to 30 days ago
- `end_date` (optional): YYYY-MM-DD format, defaults to today
- `warehouse_id` (optional): Filter by specific warehouse

**Response:**
```json
{
  "date_range": {
    "start_date": "2025-10-25",
    "end_date": "2025-11-24"
  },
  "difot": {
    "difot_percentage": 95.5,
    "total_orders": 1000,
    "on_time_in_full": 955,
    "late_deliveries": 30,
    "partial_deliveries": 15
  },
  "inventory_turnover": {
    "turnover_ratio": 8.5,
    "cogs": 1000000,
    "average_inventory_value": 117647,
    "days_inventory": 42.9
  },
  "order_fill_rate": {
    "fill_rate_percentage": 97.8,
    "total_lines": 5000,
    "filled_lines": 4890
  }
}
```

#### 2. Inventory Turnover
```
Inventory Turnover = Cost of Goods Sold / Average Inventory Value
Days Inventory = 365 / Turnover Ratio
```

#### 3. Order Fill Rate
```
Fill Rate % = (Lines shipped complete / Total order lines) × 100
```

### DIFOT Trend

**Endpoint:** `GET /api/dashboards/distributor/difot-trend/`

Returns weekly DIFOT percentages for the last 12 weeks.

**Response:**
```json
{
  "trend": [
    {
      "week": "2025-09-01",
      "difot_percentage": 94.2,
      "total_orders": 250
    },
    {
      "week": "2025-09-08",
      "difot_percentage": 95.8,
      "total_orders": 280
    }
    // ... 10 more weeks
  ]
}
```

### Business Value

- **DIFOT**: Industry benchmark is 90-95%. Scores below 90% indicate fulfillment issues.
- **Inventory Turnover**: Higher is better (6-12x for distributors). Low turnover = excess inventory.
- **Fill Rate**: Target 95%+. Low fill rate = stockouts and lost sales.

---

## Retailer Dashboard

### Overview
Retail-focused KPIs emphasize profitability, inventory efficiency, and sales performance across categories.

### Key Metrics

#### 1. GMROI (Gross Margin Return on Investment)
```
GMROI = Gross Margin / Average Inventory Cost
```

**Endpoint:** `GET /api/dashboards/retailer/`

**Query Parameters:**
- `start_date` (optional): YYYY-MM-DD
- `end_date` (optional): YYYY-MM-DD
- `category_id` (optional): Filter by product category

**Response:**
```json
{
  "date_range": {
    "start_date": "2025-10-25",
    "end_date": "2025-11-24"
  },
  "gmroi": {
    "gmroi": 3.5,
    "gross_margin": 350000,
    "average_inventory_cost": 100000
  },
  "sell_through": {
    "sell_through_percentage": 78.5,
    "units_sold": 1570,
    "units_received": 2000
  },
  "top_products": [
    {
      "product_code": "PROD-001",
      "product_name": "Widget Pro",
      "units_sold": 450,
      "revenue": 45000
    }
    // ... top 10 products
  ]
}
```

#### 2. Sell-Through Rate
```
Sell-Through % = (Units Sold / Units Received) × 100
```

#### 3. Top Selling Products
Returns the top 10 products by revenue for the period.

### Category Performance

**Endpoint:** `GET /api/dashboards/retailer/category-performance/`

Compare GMROI and sell-through across all product categories.

**Response:**
```json
{
  "categories": [
    {
      "category_id": 1,
      "category_name": "Electronics",
      "gmroi": 4.2,
      "sell_through_percentage": 82.5
    },
    {
      "category_id": 2,
      "category_name": "Apparel",
      "gmroi": 3.1,
      "sell_through_percentage": 65.0
    }
  ]
}
```

### Business Value

- **GMROI**: Target 2.5-4.0+. Shows return on inventory investment. <2.0 = poor performance.
- **Sell-Through**: Target 70-85%. High = good sales, low = overstock.
- **Top Products**: Identifies best performers for promotional focus.

---

## Manufacturer Dashboard

### Overview
Manufacturing KPIs focus on production efficiency, quality, and cost control.

### Key Metrics

#### 1. OEE (Overall Equipment Effectiveness)
```
OEE = Availability × Performance × Quality
```

Where:
- **Availability** = Operating Time / Planned Production Time
- **Performance** = Actual Output / Ideal Output
- **Quality** = Good Units / Total Units

**Endpoint:** `GET /api/dashboards/manufacturer/`

**Query Parameters:**
- `start_date` (optional): YYYY-MM-DD
- `end_date` (optional): YYYY-MM-DD
- `work_center_id` (optional): Filter by work center

**Response:**
```json
{
  "date_range": {
    "start_date": "2025-10-25",
    "end_date": "2025-11-24"
  },
  "oee": {
    "oee_percentage": 75.0,
    "availability": 90.0,
    "performance": 95.0,
    "quality": 88.0
  },
  "yield": {
    "yield_percentage": 92.5,
    "good_units": 9250,
    "total_units": 10000,
    "defective_units": 750
  },
  "cost_variance": {
    "cost_variance": -5000,
    "variance_percentage": -2.5,
    "standard_cost": 200000,
    "actual_cost": 205000,
    "favorable": false
  }
}
```

#### 2. Yield Rate
```
Yield % = (Good Units / Total Units Started) × 100
```

#### 3. Production Cost Variance
```
Variance = Standard Cost - Actual Cost
Variance % = (Variance / Standard Cost) × 100
```

### OEE Trend

**Endpoint:** `GET /api/dashboards/manufacturer/oee-trend/`

Daily OEE breakdown for the last 30 days with component metrics.

**Response:**
```json
{
  "trend": [
    {
      "date": "2025-10-25",
      "oee_percentage": 72.5,
      "availability": 88.0,
      "performance": 93.0,
      "quality": 89.0
    }
    // ... 30 days
  ]
}
```

### Business Value

- **OEE**: World-class = 85%+, Good = 60-70%, Fair = 40-60%. <40% = major issues.
- **Yield Rate**: Target 95%+. Low yield = quality problems or process issues.
- **Cost Variance**: Negative = over budget. Track to control production costs.

---

## SaaS Dashboard

### Overview
SaaS metrics track subscription revenue, customer retention, and business growth.

### Key Metrics

#### 1. MRR/ARR (Monthly/Annual Recurring Revenue)
```
MRR = Sum of all monthly recurring subscription revenue
ARR = MRR × 12
ARPU = MRR / Total Subscriptions
```

**Endpoint:** `GET /api/dashboards/saas/`

**Query Parameters:**
- `start_date` (optional): For churn calculation
- `end_date` (optional): For churn calculation

**Response:**
```json
{
  "date_range": {
    "start_date": "2025-10-25",
    "end_date": "2025-11-24"
  },
  "mrr_arr": {
    "mrr": 50000,
    "arr": 600000,
    "total_subscriptions": 250,
    "arpu": 200
  },
  "churn": {
    "customer_churn_rate": 5.2,
    "customers_lost": 13,
    "customers_at_start": 250,
    "churned_mrr": 2600
  },
  "ltv_cac": {
    "ltv": 4800,
    "cac": 600,
    "ltv_cac_ratio": 8.0,
    "arpu": 200,
    "customer_lifetime_months": 24.0
  }
}
```

#### 2. Churn Rate
```
Customer Churn Rate = (Customers Lost / Customers at Start) × 100
```

#### 3. LTV:CAC Ratio
```
LTV = ARPU × Customer Lifetime (months)
Customer Lifetime = 100 / Churn Rate
LTV:CAC Ratio = LTV / CAC
```

### MRR Trend

**Endpoint:** `GET /api/dashboards/saas/mrr-trend/`

Monthly MRR tracking for the last 12 months.

**Response:**
```json
{
  "trend": [
    {
      "month": "2024-12-01",
      "mrr": 45000,
      "total_subscriptions": 225,
      "arpu": 200
    },
    {
      "month": "2025-01-01",
      "mrr": 48000,
      "total_subscriptions": 240,
      "arpu": 200
    }
    // ... 12 months
  ]
}
```

### Cohort Analysis

**Endpoint:** `GET /api/dashboards/saas/cohort/`

**Query Parameters:**
- `cohort_month` (optional): YYYY-MM-DD, defaults to 6 months ago

Track retention rates for customers acquired in a specific month.

**Response:**
```json
{
  "cohort_month": "2025-05-01",
  "cohort_size": 50,
  "retention_by_month": {
    "month_0": 100.0,
    "month_1": 94.0,
    "month_2": 88.0,
    "month_3": 84.0,
    "month_4": 82.0,
    "month_5": 80.0
  }
}
```

### Business Value

- **MRR/ARR**: Primary growth metric. Track month-over-month growth (10%+ is strong).
- **Churn Rate**: SaaS target <5% monthly (<60% annually). High churn = product/market issues.
- **LTV:CAC**: Target 3:1 minimum. <3:1 = unsustainable growth, >3:1 = good unit economics.
- **Cohort Analysis**: Identifies retention patterns and optimal customer profiles.

---

## Service Dashboard

### Overview
Service management KPIs for tracking support quality and resolution efficiency.

### Key Metrics

#### 1. SLA Compliance Rate
```
SLA Compliance % = (Tickets within SLA / Total tickets) × 100
```

**Endpoint:** `GET /api/dashboards/service/`

**Query Parameters:**
- `start_date` (optional): YYYY-MM-DD
- `end_date` (optional): YYYY-MM-DD

**Response:**
```json
{
  "date_range": {
    "start_date": "2025-10-25",
    "end_date": "2025-11-24"
  },
  "sla_compliance": {
    "sla_compliance_rate": 92.5,
    "total_tickets": 400,
    "within_sla": 370,
    "breached_sla": 30
  },
  "mttr": {
    "mttr_hours": 4.5,
    "total_resolved": 380
  }
}
```

#### 2. MTTR (Mean Time to Resolution)
```
MTTR = Total Resolution Time / Number of Resolved Tickets
```

### Business Value

- **SLA Compliance**: Target 95%+. Low compliance = customer dissatisfaction.
- **MTTR**: Lower is better. Track by priority level (P1 < 2 hours, P2 < 8 hours, etc.).

---

## Unified Dashboard

### Overview
Get all vertical metrics in a single API call for executive dashboards.

**Endpoint:** `GET /api/dashboards/unified/`

**Query Parameters:**
- `start_date` (optional): YYYY-MM-DD
- `end_date` (optional): YYYY-MM-DD

**Response:**
Returns all vertical metrics in a single JSON response:
```json
{
  "date_range": {
    "start_date": "2025-10-25",
    "end_date": "2025-11-24"
  },
  "distributor": { /* DIFOT, turnover, fill rate */ },
  "retailer": { /* GMROI, sell-through, top products */ },
  "manufacturer": { /* OEE, yield, cost variance */ },
  "saas": { /* MRR/ARR, churn, LTV:CAC */ },
  "service": { /* SLA compliance, MTTR */ }
}
```

---

## Integration Examples

### Python Integration

```python
import requests
from datetime import date, timedelta

# Configuration
API_BASE = "https://your-erp.com/api/dashboards"
TOKEN = "your-api-token"

headers = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json"
}

# Get distributor metrics
end_date = date.today()
start_date = end_date - timedelta(days=30)

response = requests.get(
    f"{API_BASE}/distributor/",
    headers=headers,
    params={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
)

data = response.json()
print(f"DIFOT: {data['difot']['difot_percentage']}%")
print(f"Inventory Turnover: {data['inventory_turnover']['turnover_ratio']}")
```

### JavaScript/React Integration

```javascript
import React, { useState, useEffect } from 'react';
import axios from 'axios';

function DistributorDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await axios.get('/api/dashboards/distributor/', {
          params: {
            start_date: '2025-10-25',
            end_date: '2025-11-24'
          }
        });
        setMetrics(response.data);
      } catch (error) {
        console.error('Error fetching metrics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h2>DIFOT: {metrics.difot.difot_percentage}%</h2>
      <p>Orders: {metrics.difot.total_orders}</p>
      <p>On Time & In Full: {metrics.difot.on_time_in_full}</p>
    </div>
  );
}
```

### Chart.js Visualization

```javascript
import Chart from 'chart.js/auto';

// Fetch DIFOT trend data
fetch('/api/dashboards/distributor/difot-trend/')
  .then(response => response.json())
  .then(data => {
    const ctx = document.getElementById('difotChart').getContext('2d');
    
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.trend.map(d => d.week),
        datasets: [{
          label: 'DIFOT %',
          data: data.trend.map(d => d.difot_percentage),
          borderColor: 'rgb(75, 192, 192)',
          tension: 0.1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: 'DIFOT Trend (12 Weeks)'
          }
        },
        scales: {
          y: {
            beginAtZero: false,
            min: 80,
            max: 100,
            ticks: {
              callback: function(value) {
                return value + '%';
              }
            }
          }
        }
      }
    });
  });
```

### cURL Examples

```bash
# Get distributor dashboard
curl -X GET "https://your-erp.com/api/dashboards/distributor/?start_date=2025-10-25&end_date=2025-11-24" \
  -H "Authorization: Token your-api-token"

# Get SaaS metrics
curl -X GET "https://your-erp.com/api/dashboards/saas/" \
  -H "Authorization: Token your-api-token"

# Get unified dashboard
curl -X GET "https://your-erp.com/api/dashboards/unified/?start_date=2025-10-25&end_date=2025-11-24" \
  -H "Authorization: Token your-api-token"

# Get cohort analysis
curl -X GET "https://your-erp.com/api/dashboards/saas/cohort/?cohort_month=2025-05-01" \
  -H "Authorization: Token your-api-token"
```

---

## Performance Considerations

### Caching Recommendations

Dashboard calculations can be expensive. Implement caching:

```python
from django.core.cache import cache
from django.utils.hashlib import md5

def get_cached_metrics(cache_key, calculator_func, ttl=300):
    """Cache metrics for 5 minutes by default"""
    data = cache.get(cache_key)
    if data is None:
        data = calculator_func()
        cache.set(cache_key, data, ttl)
    return data

# Usage
cache_key = f"distributor_metrics_{org_id}_{start_date}_{end_date}"
metrics = get_cached_metrics(
    cache_key,
    lambda: DistributorMetrics(org).calculate_difot(start_date, end_date)
)
```

### Database Optimization

- Create indexes on frequently queried date fields
- Use `select_related()` and `prefetch_related()` to minimize queries
- Consider materialized views for complex aggregations
- Archive old data to separate tables

### Background Processing

For computationally expensive metrics, use Celery tasks:

```python
from celery import shared_task

@shared_task
def calculate_monthly_metrics(organization_id, month):
    """Pre-calculate monthly metrics overnight"""
    org = Organization.objects.get(id=organization_id)
    metrics = DistributorMetrics(org)
    
    # Calculate and cache all metrics
    # Store in database for historical reporting
```

---

## API Rate Limiting

Dashboard endpoints are rate-limited to prevent abuse:

- **Authenticated users**: 100 requests/hour
- **Dashboard endpoints**: 20 requests/minute
- **Trend endpoints**: 10 requests/minute

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1700000000
```

---

## Error Handling

### Common Error Responses

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to access this organization's data."
}
```

**400 Bad Request:**
```json
{
  "detail": "Invalid date format. Use YYYY-MM-DD."
}
```

**500 Internal Server Error:**
```json
{
  "detail": "An error occurred while calculating metrics. Please try again."
}
```

---

## Best Practices

1. **Date Ranges**: Keep date ranges reasonable (30-90 days max) for performance
2. **Caching**: Cache dashboard data for 5-15 minutes in production
3. **Pagination**: For large result sets (top products), implement pagination
4. **Monitoring**: Track slow queries and optimize as needed
5. **Historical Data**: Store daily/monthly snapshots for trend analysis
6. **Alerts**: Set up alerts when KPIs fall below thresholds

---

## Support & Troubleshooting

### Common Issues

**Q: Metrics show zero values**
- Verify data exists for the date range
- Check organization filtering is correct
- Ensure transactions are recorded properly

**Q: Slow performance**
- Reduce date range
- Check database indexes
- Enable query caching
- Use background tasks for expensive calculations

**Q: DIFOT calculation seems wrong**
- Verify shipment delivery dates are recorded
- Check SLA/estimated delivery dates are set
- Review "in full" logic (may need customization)

### Debug Mode

Enable debug logging in settings:

```python
LOGGING = {
    'loggers': {
        'dashboard.utils.vertical_metrics': {
            'level': 'DEBUG',
        }
    }
}
```

---

## Conclusion

The vertical dashboard APIs provide comprehensive KPI tracking tailored to each industry. Use these metrics to:

- Monitor business health in real-time
- Identify trends and anomalies
- Make data-driven decisions
- Track performance against benchmarks
- Power executive dashboards and reports

For additional customization or custom metrics, contact the development team.
