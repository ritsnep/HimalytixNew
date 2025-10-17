# Phase 1 Architecture Overview

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Templates (base_voucher.html + Partials)              │  │
│  │  - Journal Header Form                                  │  │
│  │  - Journal Lines Table                                  │  │
│  │  - Validation Errors                                    │  │
│  │  - Action Buttons                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    HTMX / INTERACTION LAYER                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  HTMX Handlers (Phase 2)                                │  │
│  │  - Add Line Endpoint                                    │  │
│  │  - Account Lookup                                       │  │
│  │  - Tax Calculation                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        VIEW LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  BaseVoucherView (✅ Phase 1)                          │  │
│  │  ├─ Organization Context Management                     │  │
│  │  ├─ Form Initialization                                 │  │
│  │  ├─ Request Handling (GET/POST)                        │  │
│  │  ├─ HTMX Detection                                      │  │
│  │  ├─ Response Rendering                                  │  │
│  │  └─ Audit Logging                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│  Specific Views (🔄 Phase 2):                                 │
│  ├─ VoucherCreateView                                         │
│  ├─ VoucherEditView                                           │
│  ├─ VoucherDetailView                                         │
│  └─ VoucherListView                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FORM LAYER (✅ Phase 1)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  VoucherFormFactory                                     │  │
│  │  ├─ get_journal_form()                                  │  │
│  │  ├─ get_journal_line_form()                             │  │
│  │  ├─ get_journal_line_formset()                          │  │
│  │  ├─ create_blank_line_form()                            │  │
│  │  └─ validate_forms()                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  JournalForm (✅ Enhanced - Phase 1)                   │  │
│  │  ├─ clean_journal_date() ✅ FIXED                      │  │
│  │  ├─ clean_period()                                      │  │
│  │  ├─ clean_currency_code()                               │  │
│  │  ├─ clean_exchange_rate()                               │  │
│  │  └─ cross-field validation                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  JournalLineForm (✅ Enhanced - Phase 1)               │  │
│  │  ├─ clean_debit_amount()                                │  │
│  │  ├─ clean_credit_amount()                               │  │
│  │  ├─ clean_tax_rate()                                    │  │
│  │  ├─ clean_exchange_rate()                               │  │
│  │  └─ complex validation with tax calc                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  JournalLineFormSet (✅ Phase 1)                       │  │
│  │  ├─ VoucherLineBaseFormSet                              │  │
│  │  ├─ formset-level validation                            │  │
│  │  ├─ balance checking                                    │  │
│  │  ├─ get_totals()                                        │  │
│  │  └─ get_non_deleted_forms()                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SERVICE LAYER (to be used)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  JournalValidationService                               │  │
│  │  - Complex business rule validation                     │  │
│  │  - Cross-entity validation                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  JournalPostingService (Phase 2+)                       │  │
│  │  - Post journal logic                                   │  │
│  │  - GL posting                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MODEL LAYER                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Journal                                                │  │
│  │  └─ lines (reverse relation to JournalLine)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  JournalLine                                            │  │
│  │  └─ Account, Department, Project, etc.                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Supporting Models                                      │  │
│  │  ├─ JournalType, ChartOfAccount                        │  │
│  │  ├─ AccountingPeriod, FiscalYear                       │  │
│  │  ├─ Currency, TaxCode                                  │  │
│  │  └─ Department, Project, CostCenter                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                               │
│  ├─ PostgreSQL / SQLite                                       │
│  ├─ Transactions & ACID compliance                           │
│  └─ Audit logging                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### Create New Journal Flow

```
User Request (GET)
    │
    ▼
BaseVoucherView.get()
    │
    ├─ get_organization()
    ├─ get_form() ──► VoucherFormFactory.get_journal_form()
    ├─ get_formset() ──► VoucherFormFactory.get_journal_line_formset()
    ├─ get_context_data()
    │
    ▼
render_to_response()
    │
    ▼
Browser receives HTML (base_voucher.html)
```

### Save Journal Flow

```
User submits form (POST)
    │
    ▼
BaseVoucherView.post()
    │
    ├─ Bind POST data to forms
    ├─ journal_form = get_form(data=request.POST)
    ├─ line_formset = get_formset(data=request.POST)
    │
    ├─ Validate
    ├─ journal_form.is_valid()
    │   ├─ clean_journal_date() ✅ FIXED
    │   ├─ clean_period()
    │   ├─ clean_currency_code()
    │   ├─ clean_exchange_rate()
    │   └─ cross-field validation
    │
    ├─ line_formset.is_valid()
    │   ├─ Each form:
    │   │   ├─ clean_debit_amount()
    │   │   ├─ clean_credit_amount()
    │   │   ├─ Complex validation (ONE of debit/credit)
    │   │   └─ tax calculations
    │   │
    │   └─ Formset clean():
    │       ├─ Minimum 1 line
    │       ├─ No duplicate line numbers
    │       ├─ Balance validation (debit = credit)
    │       └─ Delete tracking
    │
    ├─ Both valid?
    │
    ├─ YES:
    │   ├─ transaction.atomic()
    │   ├─ journal = journal_form.save()
    │   ├─ line_formset.instance = journal
    │   ├─ line_formset.save()
    │   ├─ save_with_audit() ──► AuditLog entry
    │   ├─ messages.success()
    │   └─ redirect(journal_detail)
    │
    └─ NO:
        ├─ render_response() with errors
        └─ User sees validation errors
```

### HTMX Add Line Flow

```
User clicks "Add Line" button
    │
    ▼
HTMX GET to /journal/htmx/add_line/
    │
    ▼
VoucherHtmxHandler.handle_add_line()
    │
    ├─ form_count = request.GET.get('form_count')
    ├─ blank_line = VoucherFormFactory.create_blank_line_form()
    │
    ▼
render() with line_form.html partial
    │
    ▼
HTMX receives HTML
    │
    ▼
Insert before #journal-lines (hx-swap="beforeend")
    │
    ▼
User sees new blank line in table
```

---

## Organization Context Flow

```
User Request
    │
    ▼
Middleware / get_active_organization()
    │
    ▼
BaseVoucherView.get_organization()
    ├─ Sets self.organization
    │
    ├─ Passed to: get_form_kwargs()
    ├─ Passed to: get_context_data()
    ├─ Passed to: JournalForm.__init__()
    ├─ Passed to: JournalLineForm.__init__()
    │
    ├─ Filters:
    │   ├─ Journal queryset
    │   ├─ JournalType choices
    │   ├─ AccountingPeriod choices
    │   ├─ ChartOfAccount choices
    │   ├─ Department choices
    │   ├─ Project choices
    │   ├─ CostCenter choices
    │   ├─ TaxCode choices
    │   └─ Currency choices
    │
    └─ Enforced in save()
        └─ journal.organization = self.get_organization()
```

---

## Validation Layers

```
Layer 1: Form Field Level
├─ debit_amount: NumberInput(min=0)
├─ credit_amount: NumberInput(min=0)
├─ journal_date: DateInput
├─ exchange_rate: NumberInput(min=0.000001)
└─ All use HTML5 constraints

Layer 2: Form clean() Level ✅ Phase 1
├─ JournalForm:
│  ├─ clean_journal_date() ✅ FIXED
│  ├─ clean_period()
│  ├─ clean_currency_code()
│  ├─ clean_exchange_rate()
│  └─ clean() for cross-field
│
├─ JournalLineForm:
│  ├─ clean_debit_amount()
│  ├─ clean_credit_amount()
│  ├─ clean_tax_rate()
│  ├─ clean_exchange_rate()
│  └─ clean() for complex logic
│      └─ ONE of debit/credit only
│
└─ JournalLineFormSet:
   ├─ Minimum lines validation
   ├─ Balance validation
   ├─ Duplicate line number detection
   └─ Delete tracking

Layer 3: Service Level (Used in Phase 2+)
└─ JournalValidationService
   ├─ Business rule validation
   ├─ Cross-entity validation
   └─ GL account balance checks

Layer 4: Database Level
└─ Constraints
   ├─ CHECK constraints
   ├─ Foreign key constraints
   └─ Unique constraints
```

---

## Form Initialization Path

```
View receives request
    │
    ▼
View calls: self.get_form()
    │
    ▼
View inherits from BaseVoucherView
    │
    ├─ super().get_form_kwargs()
    │   │
    │   └─ return {'organization': self.get_organization()}
    │
    ├─ Calls: JournalForm(**kwargs)
    │   │
    │   ├─ __init__(organization=..., data=...)
    │   │
    │   ├─ Queries filtered by organization:
    │   │   ├─ journal_type: JournalType.objects.filter(org=...)
    │   │   ├─ period: AccountingPeriod.objects.filter(org=...)
    │   │   └─ currency: Currency.objects.filter(active=True)
    │   │
    │   └─ Form ready with organization context
    │
    └─ View receives initialized form with proper querysets
```

---

## Transaction Safety

```
save_with_audit(journal, lines_data, action='create')
    │
    ▼
transaction.atomic():
    │
    ├─ Try:
    │   ├─ journal.organization = self.get_organization()
    │   ├─ journal.created_by = request.user
    │   ├─ journal.save() ──► Insert to DB
    │   ├─ _save_lines(journal, lines_data)
    │   │   └─ JournalLine.save() ──► Insert to DB
    │   ├─ _log_audit(journal, action)
    │   │   └─ AuditLog.objects.create() ──► Insert to DB
    │   └─ logger.info("Journal saved")
    │
    ├─ Success:
    │   └─ All inserts committed
    │
    └─ Exception:
        └─ All inserts rolled back
            └─ Database unchanged
```

---

## URL Resolution

```
/journal/journals/create/

    │
    ▼
Matches: urls_voucher.py
    │
    path('journals/create/', VoucherCreateView.as_view(), name='journal_create')
    │
    ▼
Dispatches to: VoucherCreateView
    │
    ├─ Inherits from BaseVoucherView
    ├─ dispatch() ──► organization check
    ├─ get() ──► GET request
    │   ├─ get_journal_form()
    │   ├─ get_journal_line_formset()
    │   ├─ get_context_data()
    │   └─ render_to_response()
    │
    └─ post() ──► POST request (Phase 2)
        ├─ Bind forms
        ├─ Validate
        ├─ Save with audit
        └─ Redirect or render errors
```

---

## Component Interaction Matrix

```
Component          Receives From          Sends To
─────────────────────────────────────────────────────
Request            Client Browser         BaseVoucherView
BaseVoucherView    Request                FormFactory, Template
FormFactory        View + Organization    Forms/Formsets
JournalForm        Factory                JournalForm clean()
JournalLineForm    Factory                FormSet clean()
JournalLineFormSet FormFactory            View
Forms/Formsets     View (POST)            Model save()
Models             Form save()            Database
Database           Model query()          Queryset
Queryset           Form __init__()        Form.fields
Template           View context()         Client Browser
Audit Log          save_with_audit()      Database
```

---

## Security Layers

```
Request
    │
    ▼
Authentication
    │
    ├─ LoginRequiredMixin
    │
    ▼
Organization Check
    │
    ├─ get_organization() in dispatch()
    ├─ Protects against missing org
    │
    ▼
Permission Check
    │
    ├─ PermissionRequiredMixin (future)
    │
    ▼
Form Validation
    │
    ├─ Field level
    ├─ Form level
    ├─ Formset level
    │
    ▼
Transaction Safety
    │
    ├─ atomic() wraps saves
    │
    ▼
Audit Logging
    │
    ├─ Every change tracked
    ├─ User recorded
    ├─ IP address recorded
    │
    ▼
Database Constraints
    │
    ├─ CHECK constraints
    ├─ Foreign key integrity
    └─ Unique constraints
```

---

## Phase 1 → Phase 2 Bridge

```
Phase 1 Complete Components:
├─ BaseVoucherView ✅
├─ VoucherFormFactory ✅
├─ Enhanced JournalForm ✅
├─ Enhanced JournalLineForm ✅
├─ JournalLineFormSet ✅
├─ URL Patterns ✅
├─ Base Templates ✅
└─ Infrastructure ✅

Phase 2 Will Implement:
├─ Concrete Views
│  ├─ VoucherCreateView
│  ├─ VoucherEditView
│  ├─ VoucherDetailView
│  └─ VoucherListView
├─ HTMX Handlers
│  ├─ add_line
│  ├─ account_lookup
│  ├─ tax_calculation
│  └─ validation
├─ Template Partials
│  ├─ journal_header_form
│  ├─ journal_lines_table
│  ├─ validation_errors
│  └─ totals_display
├─ JavaScript
│  ├─ client-side validation
│  ├─ real-time calculations
│  └─ form interactions
└─ Test Suite
   ├─ Unit tests
   ├─ Integration tests
   ├─ HTMX tests
   └─ Performance tests

All will use Phase 1 infrastructure:
Phase 2 Views ──► inherit from BaseVoucherView
Phase 2 Forms ──► created via VoucherFormFactory
Phase 2 Templates ──► extend base_voucher.html
Phase 2 HTMX ──► uses standardized URLs
```

---

## Key Design Decisions

```
1. Factory Pattern
   ├─ Ensures consistent form creation
   ├─ Single point for form customization
   └─ Easy to add new logic

2. Mixins
   ├─ VoucherListMixin for list views
   ├─ VoucherDetailMixin for detail views
   └─ Promotes code reuse

3. Organization Context Everywhere
   ├─ Prevents data leakage
   ├─ Multi-tenancy safe
   └─ Enforced at every layer

4. Layered Validation
   ├─ Field level (HTML5)
   ├─ Form level (Python)
   ├─ Formset level (Logic)
   └─ Service level (Business rules)

5. HTMX-First
   ├─ All interactions progressive
   ├─ Works without JavaScript
   └─ Server renders fragments

6. Comprehensive Logging
   ├─ All changes recorded
   ├─ User tracking
   ├─ IP address logging
   └─ Compliance ready
```

---

**Version**: 1.0.0
**Date**: October 16, 2025
**Status**: Phase 1 Complete
