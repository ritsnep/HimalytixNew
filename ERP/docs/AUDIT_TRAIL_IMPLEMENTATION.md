# Audit Trail & Activity Log Implementation Guide

## Overview

The Himalytix ERP system now includes a comprehensive Audit Trail system that tracks all important changes across financial and operational records, with multi-tenant isolation, hash-chaining for immutability verification, and role-based access controls.

## Features

### 1. **Automatic Change Tracking (Django Signals)**

All changes to critical models are automatically logged via Django signals:

- **Accounting Models**: Journal, JournalLine, SalesOrder, SalesInvoice, GeneralLedgerEntry, DeliveryChallan, BudgetLine, FixedAsset, etc.
- **Purchasing Models**: PurchaseOrder, GoodsReceipt, PurchaseInvoice, LandedCostDocument, etc.

**What's Captured**:
- WHO: User making the change
- WHAT: Model name, object ID, field-level changes (before/after)
- WHEN: Timestamp (auto)
- WHERE: IP address, browser user agent
- ACTION: create, update, delete, export, print, approve, reject, post, sync

### 2. **Login Event Tracking**

Enhanced login monitoring with `LoginEventLog` model tracking:
- Successful/failed login attempts
- Authentication method (email, Google, SAML, API token)
- MFA usage (TOTP, SMS, Email, Backup codes)
- IP address and user agent
- Risk scoring and anomaly detection
- Geographic location (optional)

**Automatic Triggers**:
- On user login success → logs with IP/user-agent
- On failed authentication → logs failure reason
- Background task detects suspicious patterns (>5 failures per IP)

### 3. **Activity Log Admin Dashboard**

Django admin interface at `/admin/accounting/auditlog/` with:

- **Read-only view**: No modification/deletion except by superadmin (for compliance)
- **Advanced filtering**: By date range, user, action type, model, organization
- **Search**: By username, email, IP, or description
- **Colored badges**: Visual action type indicators (Create=green, Delete=red, etc.)
- **Expandable details**: View full change JSON, network info, hash-chain status
- **CSV export**: Download filtered logs as CSV (with access control)
- **Organization scoping**: Non-superusers only see their org's logs

**Access Control**:
- Required: `is_staff=True` AND (superuser OR `role in ['superadmin', 'admin']`)
- Read-only enforced at model level
- Deletion restricted to superusers only

### 4. **Immutability & Hash-Chaining (ADR-003)**

Optional cryptographic verification for compliance:

- **Content Hash**: SHA-256 of each audit record
- **Previous Hash Link**: References previous record in chain
- **Tamper Detection**: Verify integrity via `verify_audit_chain()`
- **Sealing**: Convert unsealed logs to immutable via management command

**Manual Sealing**:
```bash
# Seal logs older than 24 hours
python manage.py seal_audit_logs --days 1

# For specific organization
python manage.py seal_audit_logs --organization 5

# Batch via Celery (async)
python manage.py seal_audit_logs_batch  # Scheduled nightly
```

### 5. **Data Retention & Archival**

Manage audit log lifecycle:

**Retention Policy** (Configurable):
- Active logs: Unbounded (queryable in admin/API)
- Archive threshold: 12 months (default)
- Archival method: JSON export to disk (with option for audit_log_archive table)

**Management Command**:
```bash
# Dry-run (see what would happen)
python manage.py archive_audit_logs --days 365 --dry-run

# Archive logs older than 1 year
python manage.py archive_audit_logs --days 365 --action archive

# Delete logs older than 2 years (irreversible)
python manage.py archive_audit_logs --days 730 --action delete
```

Creates timestamped JSON files: `audit_archive_20250111_143022.json`

### 6. **Asynchronous Audit Tasks (Celery)**

For high-volume events, audit writes are queued asynchronously:

```python
from accounting.tasks import log_audit_event_async

# In signal handler or view
log_audit_event_async.delay(
    user_id=user.id,
    action='create',
    content_type_id=ContentType.objects.get_for_model(Invoice).id,
    object_id=invoice.id,
    changes={'total': 1000.0},
    organization_id=org.id
)
```

**Scheduled Tasks** (in Celery Beat):
```python
# Seal audit logs nightly
seal_audit_logs_batch.apply_async(countdown=3600)  # Run in 1 hour

# Check for suspicious login activity daily
check_suspicious_login_activity.apply_async(countdown=86400)
```

### 7. **REST API for Audit Retrieval**

**Endpoint**: `GET /api/accounting/audit-logs/`

**Features**:
- List all audit logs with pagination
- Advanced filtering (date range, user, action, model)
- Full-text search by username, email, IP
- Export to CSV/JSON
- Summary statistics
- User activity breakdown
- Entity history (full change timeline for one object)
- Hash-chain integrity verification

**Example Requests**:

```bash
# List latest 10 audit logs
curl "http://localhost:8000/api/accounting/audit-logs/?limit=10"

# Filter by date range and action
curl "http://localhost:8000/api/accounting/audit-logs/?timestamp_from=2025-01-01&timestamp_to=2025-01-31&action=create"

# Search for user activity
curl "http://localhost:8000/api/accounting/audit-logs/?user=john"

# Get summary statistics (last 7 days)
curl "http://localhost:8000/api/accounting/audit-logs/summary/?days=7"

# Get one user's activity
curl "http://localhost:8000/api/accounting/audit-logs/user_activity/?user_id=42&days=30"

# Get full history of one invoice
curl "http://localhost:8000/api/accounting/audit-logs/entity_history/?model=invoice&object_id=100"

# Verify hash-chain integrity
curl -X POST "http://localhost:8000/api/accounting/audit-logs/verify_integrity/" \
  -H "Content-Type: application/json" \
  -d '{"log_ids": [1, 2, 3]}'

# Export to CSV
curl "http://localhost:8000/api/accounting/audit-logs/export/?format=csv" \
  -o audit_logs.csv

# Export with date range
curl "http://localhost:8000/api/accounting/audit-logs/export/?timestamp_from=2025-01-01&timestamp_to=2025-01-31&format=json" \
  -o audit_logs.json
```

## Models & Fields

### AuditLog

```python
class AuditLog(models.Model):
    timestamp          # Auto-set, indexed
    user               # FK → CustomUser
    organization       # FK → Organization (for multi-tenant isolation)
    action             # 'create', 'update', 'delete', 'export', 'print', 'approve', 'reject', 'post', 'sync'
    content_type       # FK → ContentType (for generic auditing)
    object_id          # Integer ID of audited object
    content_object     # GenericForeignKey
    changes            # JSON: {'field': {'old': value, 'new': value}}
    details            # Text description (optional)
    ip_address         # GenericIPAddressField
    
    # Hash-chaining (for immutability)
    content_hash       # SHA-256 hash (null until sealed)
    previous_hash      # FK → AuditLog (null for first in chain)
    is_immutable       # Boolean (prevents modification once sealed)
```

### LoginEventLog

```python
class LoginEventLog(models.Model):
    user               # FK → CustomUser
    organization       # FK → Organization (null=True)
    event_type         # 'login_success', 'login_failed_invalid_creds', 'logout', etc.
    ip_address         # GenericIPAddressField
    user_agent         # Browser/client info (truncated to 1KB)
    session_id         # Session token (if applicable)
    auth_method        # 'email', 'google', 'facebook', 'saml', 'api_token'
    mfa_method         # 'totp', 'sms', 'email', 'backup_code' (nullable)
    timestamp          # Auto-set, indexed
    login_duration     # DurationField (from login to logout)
    failure_reason     # Text (why login failed)
    is_suspicious      # Boolean (anomaly flag)
    risk_score         # SmallInteger (0-100)
    country_code       # Two-letter code (optional)
    city               # City name (optional)
```

## Configuration

### Enable/Disable Auditing

Audit logging is **always on** for registered models. To exclude a model:

1. Remove from `AUDITED_MODELS` tuple in `accounting/signals/__init__.py`
2. Or remove signal connection in `purchasing/signals.py`

### Async vs. Synchronous

**Default**: Synchronous (in-band with request)

**To enable async** for specific models:

```python
# In signal handler
@receiver(post_save, sender=HighVolume Model)
def _audit_post_save(sender, instance, created, **kwargs):
    if created:
        log_audit_event_async.delay(...)  # Queue instead of inline
```

### Hash-Chaining Frequency

**Default**: Only seal logs on-demand via management command

**To automate** via Celery:

```python
# In celerybeat schedule (settings.py)
from celery.schedules import crontab

app.conf.beat_schedule = {
    'seal-audit-logs-nightly': {
        'task': 'accounting.tasks.seal_audit_logs_batch',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'args': (None, 1000),  # All orgs, batch of 1000
    },
    'check-suspicious-logins': {
        'task': 'accounting.tasks.check_suspicious_login_activity',
        'schedule': crontab(hour=6, minute=0),  # 6 AM daily
    },
}
```

## Usage Examples

### View Audit Trail in Admin

1. Navigate to `/admin/accounting/auditlog/`
2. Filter by:
   - **Date range**: Use "Timestamp" filter
   - **User**: Select from dropdown or search
   - **Action type**: Create, Update, Delete, etc.
   - **Organization**: Multi-tenant filter
3. Click log entry to see full details (expandable sections)
4. Select logs and export as CSV

### Programmatic Access

```python
from accounting.models import AuditLog
from accounting.utils.audit_integrity import (
    get_audit_summary, get_user_activity, get_entity_history, 
    verify_audit_chain, compute_content_hash
)

# Get summary for org
summary = get_audit_summary(organization=my_org, days=30)
print(summary['by_action'])  # {'create': 150, 'update': 42, 'delete': 3}

# Get user's activity
user_activity = get_user_activity(user=john, days=7)
print(user_activity['total_actions'])  # 42

# Get full history of one invoice
history = get_entity_history(
    content_type=ContentType.objects.get_for_model(Invoice),
    object_id=100,
    organization=my_org
)
for log in history:
    print(f"{log.timestamp}: {log.action} by {log.user}")

# Verify hash-chain integrity
is_valid, error = verify_audit_chain(log)
if not is_valid:
    print(f"TAMPERING DETECTED: {error}")
```

### Log Custom Events

```python
from accounting.signals import log_change

# Manual logging outside of signal handlers
log_change(
    instance=invoice,
    action='export',
    changes={'format': 'pdf', 'filename': 'INV-2025-001.pdf'}
)
```

## Permissions & Access Control

### Admin Access

User must have ALL of:
- `is_staff=True` (Django auth)
- `is_superuser=True` OR `role in ['superadmin', 'admin']` (Himalytix RBAC)

Non-superusers are restricted to their organization's logs.

### API Access

```python
from rest_framework.permissions import IsAuthenticated, BasePermission

class CanViewAuditLog(BasePermission):
    message = "You do not have permission to view audit logs."
    def has_permission(self, request):
        return AuditLogPermissionChecker.can_view(request.user)

class CanExportAuditLog(BasePermission):
    message = "You do not have permission to export audit logs."
    def has_permission(self, request):
        return AuditLogPermissionChecker.can_export(request.user)
```

Export restricted to superusers/admins only.

## Performance Considerations

### Indexing

Audit logs are indexed on:
- `organization + timestamp` (org summary queries)
- `user + timestamp` (user activity)
- `timestamp` (time-range queries)
- `content_type + object_id` (entity history)
- `action` (action breakdown)

### Query Optimization

```python
# GOOD: Use select_related for FK access
logs = AuditLog.objects.select_related('user', 'organization', 'content_type')

# BETTER: Use prefetch_related if many-to-one reverses
# (Not typical for AuditLog)
```

### High-Volume Mitigation

1. **Async queuing**: Queue GL entries to Celery instead of inline
2. **Partitioning**: Archive old logs to separate tables/files
3. **Sampling**: For certain high-frequency models, sample every Nth change (optional)
4. **Pruning**: Delete logs older than retention policy

## Troubleshooting

### Signals Not Firing

- Check that app `ready()` method imports signals
- Verify model is in `AUDITED_MODELS` tuple
- Ensure signal registration happens before data modification

### Hash-Chaining Not Working

- Call `seal_audit_logs.py` management command
- Verify `content_hash` field was added via migration
- Check that `is_immutable=True` flags records correctly

### Login Events Not Appearing

- Ensure `LoginEventLog` model exists (created via migration)
- Check that `user_login_failed` signal is connected in `usermanagement/signals.py`
- Verify user auth backend is calling Django signals (not custom auth)

### API Filtering Slow

- Ensure indexes are created (run migrations)
- Use pagination (default: 20/page)
- Avoid unindexed filters like custom JSON keys

## Migration Steps

### 1. Create Models

```bash
# After model definitions are added
python manage.py makemigrations accounting
python manage.py makemigrations usermanagement
python manage.py migrate
```

### 2. Register Signals

- Accounting signals: Already registered in `accounting/signals/__init__.py`
- Purchasing signals: Call `signals.py` from `purchasing/apps.py`
- Login events: Call `signals.py` from `usermanagement/apps.py`

### 3. Create Admin Classes

- `AuditLogAdmin` already registered in `accounting/admin.py`
- `LoginEventLogAdmin` (optional, can add if needed)

### 4. Register API Endpoints

- Already added to `accounting/api/urls.py` as `/audit-logs/`

### 5. Schedule Celery Tasks (Optional)

Add to `settings.py` if using Celery Beat:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'seal-audit-logs': {
        'task': 'accounting.tasks.seal_audit_logs_batch',
        'schedule': crontab(hour=2, minute=0),
    },
}
```

## Testing

```bash
# Run audit signal tests
python manage.py test accounting.tests.test_audit_signals

# Test API endpoints
python manage.py test accounting.tests.test_audit_api

# Test hash-chaining
python manage.py test accounting.tests.test_audit_integrity
```

## Security Best Practices

1. **Access Control**: Regularly audit who has `is_staff` and admin roles
2. **Retention**: Delete logs older than legal hold period
3. **Immutability**: Seal logs older than 24 hours via Celery
4. **Monitoring**: Check for spike in delete actions (unusual)
5. **Export Control**: Require superuser for CSV/JSON exports
6. **IP Tracking**: Review logins from suspicious IPs
7. **MFA Monitoring**: Track MFA usage and failures

## Future Enhancements

1. **Real-time Notifications**: WebSocket alerts to admins on critical actions
2. **Advanced Analytics**: Dashboard with trend charts (actions over time)
3. **Compliance Reporting**: Pre-built reports for SOC 2, GDPR, local audits
4. **Automated Alerts**: Trigger webhook on high-value transactions or sensitive deletes
5. **Blockchain Audit**: Option to anchor audit hashes to blockchain for external verification
6. **Geolocation Alerts**: Notify on logins from new countries
7. **Custom Audit Policies**: Allow org admins to define what to audit
8. **Audit Trail Snapshots**: Weekly summaries emailed to admins

## References

- ADR-003: Hash-Chained Immutable Audit Logs
- Django Signals: https://docs.djangoproject.com/en/stable/topics/signals/
- Django Admin Customization: https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- DRF Filtering: https://www.django-rest-framework.org/api-guide/filtering/
