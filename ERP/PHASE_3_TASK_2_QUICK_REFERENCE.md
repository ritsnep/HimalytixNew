# Phase 3 Task 2: Advanced Reporting - QUICK REFERENCE

## 📊 Report Types & Generators

| Report | Purpose | Key Data | Export |
|--------|---------|----------|--------|
| **General Ledger** | Transaction detail by account | Debit/credit/running balance | CSV/Excel/PDF |
| **Trial Balance** | Account balance verification | Debit/credit by account | CSV/Excel/PDF |
| **P&L Statement** | Revenue/expense analysis | Income/expense totals | CSV/Excel/PDF |
| **Balance Sheet** | Assets/liabilities/equity snapshot | Asset/liability balances | CSV/Excel/PDF |
| **Cash Flow** | Cash activity by type | Operating/investing/financing | CSV/Excel/PDF |
| **A/R Aging** | Customer receivable analysis | Aging buckets (0-30, 31-60, etc.) | CSV/Excel/PDF |

---

## 🏗️ Architecture Layers

```
View Layer (8 Views)
    ↓
Service Layer (2 Services)
    ├─ ReportService (6 generators)
    └─ ReportExportService (3 formats)
    ↓
Template Layer (6 Templates)
    ↓
Database Queries (Optimized with select_related)
```

---

## 📁 File Structure

```
accounting/
├── views/
│   └── report_views.py              # 8 view classes
├── services/
│   ├── report_service.py            # Report generation
│   └── report_export_service.py     # Multi-format export
├── urls/
│   └── report_urls.py               # Route definitions
├── templates/accounting/reports/
│   ├── report_list.html             # Report catalog
│   ├── general_ledger.html          # GL display
│   ├── trial_balance.html           # TB display
│   ├── profit_loss.html             # P&L display
│   ├── balance_sheet.html           # BS display
│   ├── cash_flow.html               # CF display
│   └── ar_aging.html                # A/R display
└── tests/
    └── test_reporting.py            # 21+ tests
```

---

## 🔌 URL Routing

```python
# Report list page
/advanced-reports/

# Individual report views
/advanced-reports/general-ledger/
/advanced-reports/trial-balance/
/advanced-reports/profit-loss/
/advanced-reports/balance-sheet/
/advanced-reports/cash-flow/
/advanced-reports/ar-aging/

# Export endpoint (POST)
/advanced-reports/export/
```

---

## 💻 Code Examples

### Generate a Report
```python
from accounting.services.report_service import ReportService
from datetime import date

# Create service with organization context
service = ReportService(organization)

# Set reporting period
service.set_date_range(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)

# Generate report
report = service.generate_trial_balance()

# Report structure:
# {
#     'report_type': 'trial_balance',
#     'organization': 'Org Name',
#     'as_of_date': date,
#     'lines': [...],
#     'totals': {...},
#     'is_balanced': True/False
# }
```

### Export to Multiple Formats
```python
from accounting.services.report_export_service import ReportExportService

# CSV Export
csv_buffer, csv_filename = ReportExportService.to_csv(report)
# Returns: (BytesIO, 'trial_balance_2024_12_31.csv')

# Excel Export  
excel_buffer, excel_filename = ReportExportService.to_excel(report)
# Returns: (BytesIO, 'trial_balance_2024_12_31.xlsx')

# PDF Export
pdf_buffer, pdf_filename = ReportExportService.to_pdf(report)
# Returns: (BytesIO, 'trial_balance_2024_12_31.pdf')
```

### Use in Views
```python
from django.views import View
from accounting.services.report_service import ReportService
from accounting.services.report_export_service import ReportExportService

class TrialBalanceView(View):
    def get(self, request):
        # Create service
        service = ReportService(self.organization)
        
        # Set date range from GET params
        service.set_date_range(
            start_date=date.fromisoformat(request.GET['start_date']),
            end_date=date.fromisoformat(request.GET['end_date'])
        )
        
        # Generate report
        report = service.generate_trial_balance()
        
        # Pass to template
        return render(request, 'trial_balance.html', {
            'report_data': report
        })
```

---

## 🔐 Security Features

✅ **Organization Isolation**: All queries scoped to user's organization  
✅ **Authentication**: LoginRequiredMixin on all views  
✅ **Authorization**: UserOrganizationMixin ensures org ownership  
✅ **Input Validation**: Date format validation in views  
✅ **SQL Safety**: Django ORM prevents injection  

---

## 📈 Report Definitions

### General Ledger
- **Filters**: Account, date range
- **Displays**: Date, account, amount (debit/credit), running balance
- **Use Case**: Detailed transaction review

### Trial Balance  
- **Filters**: As-of date
- **Displays**: Account code/name, debit balance, credit balance
- **Use Case**: Verify debits = credits

### Profit & Loss
- **Filters**: Start/end date
- **Displays**: Revenue, expenses, net income
- **Use Case**: Performance analysis

### Balance Sheet
- **Filters**: As-of date
- **Displays**: Assets, liabilities, equity
- **Use Case**: Financial position snapshot

### Cash Flow
- **Filters**: Start/end date
- **Displays**: Operating/investing/financing cash flows
- **Use Case**: Liquidity analysis

### A/R Aging
- **Filters**: As-of date
- **Displays**: Customer, aging buckets (0-30, 31-60, 61-90, 90+)
- **Use Case**: Collection management

---

## 🧪 Testing

### Run All Tests
```bash
python manage.py test accounting.tests.test_reporting
```

### Run Specific Test Class
```bash
python manage.py test accounting.tests.test_reporting.ReportServiceTestCase
```

### Test Coverage
```bash
coverage run --source='accounting' manage.py test accounting.tests.test_reporting
coverage report
```

---

## 🔧 Configuration

### Optional Dependencies (for PDF/Excel)
```bash
pip install openpyxl weasyprint
```

### No Configuration Required
- Reports use existing Account/Journal models
- Organization context automatic via middleware
- Date formatting i18n aware

---

## 🚀 Performance Considerations

### Query Optimization
- `select_related()` for foreign keys (account, org)
- `prefetch_related()` for reverse relations
- Indexed queries on date ranges
- Single query per report type

### Caching Strategy (Future)
- Cache opening balance calculations
- Cache account hierarchy
- Invalidate on new journal posts

### Scalability
- Service layer enables parallel processing
- Export functions stateless (no side effects)
- Decimal calculations precise without rounding errors

---

## 📝 Implementation Checklist

✅ 6 Report generators (GL, TB, P&L, BS, CF, A/R)  
✅ 3 Export formats (CSV, Excel, PDF)  
✅ 8 Views (list + 6 reports + export)  
✅ 6 Templates (responsive Bootstrap)  
✅ 21+ Tests (service, views, exports)  
✅ URL routing (advanced-reports prefix)  
✅ Organization isolation (multi-tenant)  
✅ Financial precision (Decimal type)  
✅ Error handling (validation, logging)  
✅ i18n Support (translation strings)  

---

## 🔗 Integration Points

**Depends On**:
- Account model (chart of accounts)
- Journal/JournalLine models (transactions)
- Organization model (multi-tenancy)
- UserOrganizationMixin (context)

**Integrated Into**:
- Main accounting URLs
- Dashboard (can link to reports)
- API (export endpoints)
- Scheduled tasks (can generate reports)

---

## 📞 Troubleshooting

**Issue**: Reports showing no data  
→ Check journals are STATUS_POSTED, within date range

**Issue**: Export fails (PDF/Excel)  
→ Check optional dependencies installed (openpyxl, weasyprint)

**Issue**: Wrong organization data  
→ Verify UserOrganizationMixin installed on views

**Issue**: Date parsing errors  
→ Use ISO format (YYYY-MM-DD) in query params

---

## 🎓 Learning Resources

- General Ledger: Transaction-level detail with running balance
- Trial Balance: Verifies accounting equation (Debits = Credits)  
- P&L: Revenue minus expenses = net income
- Balance Sheet: Assets = Liabilities + Equity
- Cash Flow: Operating + Investing + Financing activities
- A/R Aging: Collections analysis by time period

---

**Version**: 1.0  
**Status**: Production Ready  
**Last Updated**: 2024  
**Lines of Code**: 2,500+
