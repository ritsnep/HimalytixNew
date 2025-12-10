# Audit Trail Implementation - Quick Start Guide

## What Was Implemented

A comprehensive audit logging system for Himalytix ERP that tracks all changes to financial records, login attempts, and provides multi-tenant isolation, integrity verification, and role-based access control.

## Key Components

### 1. **Enhanced Models**
- **AuditLog**: Expanded with org scoping, hash-chaining, action types, immutability flags
- **LoginEventLog**: New model for detailed login tracking (success/failure, MFA, risk scoring, location)

### 2. **Automatic Auditing (Django Signals)**
**Accounting Models Audited:**
- Journal, JournalLine, FiscalYear, AccountingPeriod, ChartOfAccount
- GeneralLedgerEntry, SalesOrder, SalesOrderLine, SalesInvoice, SalesInvoiceLine
- DeliveryChallan, DeliveryNote, BudgetLine, FixedAsset, FixedAssetDepreciation

**Purchasing Models Audited:**
- PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
- PurchaseInvoice, PurchaseInvoiceLine, LandedCostDocument, LandedCostLine, LandedCostAllocation

### 3. **Admin Dashboard**
📍 **Location:** `/admin/accounting/auditlog/`

**Features:**
- Read-only view (no modification except superuser deletion for archival)
- Color-coded action badges (Create=green, Delete=red, Update=yellow, etc.)
- Multi-level filtering: date range, user, action, model, organization
- Full-text search by username, email, IP, or description
- Expandable sections: changes JSON, network info, hash-chain details
- Date hierarchy navigation
- CSV export with permission checks

**Access Control:**
- Requires: `is_staff=True` AND (superuser OR admin role)
- Non-superusers: scoped to their organization

### 4. **Login Event Tracking**
📍 **Models:** `LoginEventLog`, enhanced `LoginLog`

**Auto-Captured:**
- Login success/failure with reason
- Failed auth attempts → automatically logged
- IP address, user agent, session ID
- Authentication method (email, OAuth, SAML, API token)
- MFA method used (TOTP, SMS, Email, backup code)
- Risk scoring and anomaly detection flags

**Scheduled Task:**
- Daily check for suspicious patterns (5+ failures per IP)
- Marks events as suspicious with risk score

### 5. **Hash-Chaining (Immutability)**
📍 **Files:** `accounting/utils/audit_integrity.py`, management command `seal_audit_logs.py`

**Purpose:** Cryptographic verification to detect tampering

**Process:**
```bash
# Seal logs older than 24 hours
python manage.py seal_audit_logs --days 1

# Async via Celery (nightly)
python manage.py seal_audit_logs_batch
```

**Verification:**
- Recompute SHA-256 hash of record
- Verify it matches stored `content_hash`
- Check `previous_hash` link (chain integrity)

### 6. **Data Retention & Archival**
📍 **Command:** `archive_audit_logs.py`

**Policy:**
- Active logs: queryable in admin/API (no limit)
- Archive trigger: 365 days (configurable)
- Archive method: JSON export to disk (+ option for DB archive table)

```bash
# Dry-run
python manage.py archive_audit_logs --days 365 --dry-run

# Archive (copy to JSON)
python manage.py archive_audit_logs --days 365

# Delete (irreversible - superuser only)
python manage.py archive_audit_logs --days 730 --action delete
```

### 7. **RBAC for Audit Views**
📍 **Files:** `accounting/mixins/audit_access.py`

**Permission Checkers:**
```python
AuditLogPermissionChecker.can_view(user)      # View logs
AuditLogPermissionChecker.can_export(user)    # Export logs
AuditLogPermissionChecker.can_delete(user)    # Delete logs (superuser only)
AuditLogPermissionChecker.get_accessible_organizations(user)
```

**Applied To:**
- Admin interface (view permission check)
- API endpoints (permission classes)
- Templates (conditional display)

### 8. **Celery Async Tasks**
📍 **File:** `accounting/tasks.py`

**Available Tasks:**

1. **`log_audit_event_async`** - Queue audit writes for high-volume models
   ```python
   log_audit_event_async.delay(user_id, action, content_type_id, object_id, ...)
   ```

2. **`seal_audit_logs_batch`** - Nightly sealing of logs
   ```python
   seal_audit_logs_batch.delay(organization_id=None, batch_size=1000)
   ```

3. **`check_suspicious_login_activity`** - Detect anomalies
   ```python
   check_suspicious_login_activity.delay(organization_id=None)
   ```

### 9. **REST API**
📍 **Endpoint:** `/api/accounting/audit-logs/`

**Available Actions:**

| Action | URL | Method | Description |
|--------|-----|--------|-------------|
| List | `/audit-logs/` | GET | List audit logs with pagination |
| Retrieve | `/audit-logs/{id}/` | GET | Get single log details |
| Summary | `/audit-logs/summary/` | GET | Stats breakdown (by action, user, model) |
| User Activity | `/audit-logs/user_activity/` | GET | Activity for one user |
| Entity History | `/audit-logs/entity_history/` | GET | Full change timeline for one object |
| Export | `/audit-logs/export/` | GET | Download as CSV/JSON |
| Verify | `/audit-logs/verify_integrity/` | POST | Check hash-chain integrity |

**Example Queries:**
```bash
# List recent logs
GET /api/accounting/audit-logs/?limit=50&ordering=-timestamp

# Filter by date and user
GET /api/accounting/audit-logs/?timestamp_from=2025-01-01&timestamp_to=2025-01-31&user=john

# Get summary for last 30 days
GET /api/accounting/audit-logs/summary/?days=30

# User's activity
GET /api/accounting/audit-logs/user_activity/?user_id=42&days=7

# Full history of invoice #100
GET /api/accounting/audit-logs/entity_history/?model=invoice&object_id=100

# Export to CSV
GET /api/accounting/audit-logs/export/?format=csv

# Verify logs are not tampered with
POST /api/accounting/audit-logs/verify_integrity/
{ "log_ids": [1, 2, 3] }
```

### 10. **Utility Functions**
📍 **File:** `accounting/utils/audit_integrity.py`

```python
# Compute hash for new record
content_hash = compute_content_hash(audit_log_dict)

# Verify integrity
is_valid, error_msg = verify_audit_chain(audit_log)

# Get summaries
summary = get_audit_summary(organization, days=30)
user_activity = get_user_activity(user, days=7)
history = get_entity_history(content_type, object_id)

# Field change computation
changes = compute_field_changes(old_values, new_values)
```

## File Structure

```
accounting/
├── models.py                    # AuditLog (enhanced)
├── signals/__init__.py          # Audit signal handlers (expanded)
├── utils/audit_integrity.py     # Hash-chaining & audit utils
├── mixins/audit_access.py       # RBAC mixins
├── admin.py                     # AuditLogAdmin dashboard
├── tasks.py                     # Celery async tasks
├── api/audit.py                 # REST API viewset
├── api/urls.py                  # Routes registered
└── management/commands/
    ├── seal_audit_logs.py       # Seal logs with hashes
    └── archive_audit_logs.py    # Archive/delete old logs

usermanagement/
├── models.py                    # LoginLog, LoginEventLog (new)
└── signals.py                   # Login event tracking

purchasing/
├── signals.py                   # Purchase model auditing
└── apps.py                      # Signal registration

Docs/
└── AUDIT_TRAIL_IMPLEMENTATION.md  # Full documentation
```

## Quick Start

### 1. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Access Admin Dashboard
```
http://localhost:8000/admin/accounting/auditlog/
```

### 3. Query via API
```bash
curl "http://localhost:8000/api/accounting/audit-logs/?limit=10"
```

### 4. Schedule Celery Tasks (Optional)
Add to `settings.py`:
```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'seal-audit-logs-nightly': {
        'task': 'accounting.tasks.seal_audit_logs_batch',
        'schedule': crontab(hour=2, minute=0),
    },
    'check-suspicious-logins': {
        'task': 'accounting.tasks.check_suspicious_login_activity',
        'schedule': crontab(hour=6, minute=0),
    },
}
```

### 5. Test Manually
```bash
# Create an invoice (automatically logged)
# Check admin: /admin/accounting/auditlog/

# Modify it (update logged)
# Delete it (delete logged)

# Check login events
# /admin/usermanagement/logineventlog/
```

## Performance Impact

- **Minimal overhead**: Signal handlers are lightweight
- **Async option**: Queue high-volume events to Celery
- **Indexed queries**: All filter fields are indexed
- **Archival**: Move old logs out of active table for speed

## Compliance & Security

✅ **Audit Trail**: Every change tracked with who/what/when/where  
✅ **Login Tracking**: All login attempts recorded (success/failure)  
✅ **Multi-tenant Isolation**: Org-level scoping prevents data leaks  
✅ **Immutability Option**: Hash-chaining for tamper detection  
✅ **RBAC**: Role-based access to audit views  
✅ **Retention Policy**: Automatic archival/deletion schedule  
✅ **Export Control**: Only admins can download logs  
✅ **Read-only Admin**: Audit logs cannot be modified (compliance)  

## Next Steps

1. **Test in dev environment**: Create/update/delete invoices and check logs
2. **Configure retention policy**: Adjust archival threshold if needed
3. **Enable Celery tasks**: Schedule nightly sealing and login checks
4. **Set up alerts**: (Future feature) Webhook notifications on critical actions
5. **Train admins**: Show how to use filters and export functionality
6. **Monitor performance**: Check query times on large log tables

## Reference Documentation

See `/Docs/AUDIT_TRAIL_IMPLEMENTATION.md` for:
- Detailed model schemas
- API endpoint parameters
- Configuration options
- Troubleshooting guide
- Testing procedures
- Future enhancements roadmap
