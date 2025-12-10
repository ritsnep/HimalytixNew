# Audit Log UI - Dason Template Integration

## Overview

A professional, user-friendly Audit Log interface has been created using the Dason Admin Template framework (consistent with the rest of the Himalytix ERP software UI). This replaces the Django admin panel audit log view with a modern, feature-rich dashboard accessible to authorized users.

## Features Implemented

### 1. **Audit Log List View** (`/accounting/audit-logs/`)
   - **Responsive table** displaying all audit logs with key information
   - **Advanced filtering** by:
     - Date range (from/to)
     - User
     - Action type
     - Search (across details and user names)
   - **Pagination**: 50 logs per page
   - **Action badges** with color coding:
     - 🟢 Create (green)
     - 🔵 Update (blue)
     - 🔴 Delete (red)
     - 🔷 Other actions (info)
   - **Status indicators**: Sealed/Active status with lock icons
   - **Quick actions**: View detail button for each entry
   - **Export options**: CSV and JSON export with filters applied

### 2. **Audit Log Detail View** (`/accounting/audit-logs/<id>/`)
   - **Event Information** section showing:
     - Action type with color badge
     - Precise timestamp with relative time
     - Affected entity and object ID
     - Organization scope
     - Event details/narration
   
   - **Changes Comparison** section:
     - Field-by-field breakdown
     - Before/after values displayed side-by-side
     - Color-coded diff display
   
   - **User Information** sidebar:
     - User avatar with initials
     - User name and email
     - Quick link to view all user changes
   
   - **Network Information**:
     - IP address from which action was performed
     - Session identifier
   
   - **Integrity Status**:
     - Seal status (sealed = immutable)
     - Content hash for verification
     - Hash-chain reference (link to previous entry)
   
   - **Related Links**:
     - View same model changes
     - View user activity
     - View audit summary

### 3. **Audit Summary Dashboard** (`/accounting/audit-logs/summary/`)
   
   **Key Statistics Cards**:
   - Total audit logs in period
   - Active users
   - Modified models count
   - Date range selector
   
   **Daily Activity Chart**:
   - Line chart showing audit events over time
   - Interactive with Chart.js
   - Hover to see daily counts
   
   **Action Breakdown**:
   - Pie/progress chart showing distribution of actions
   - Create, Update, Delete, etc. with counts
   
   **Most Active Users**:
   - Ranked list of users by activity
   - Progress bars showing relative activity
   - Clickable to filter audit logs by user
   
   **Most Modified Models**:
   - Ranked list of models with most changes
   - Counts and progress indicators
   - Links to view changes for specific models

## Technical Implementation

### Views (`accounting/views/audit_log_views.py`)

```python
class AuditLogListView(LoginRequiredMixin, UserOrganizationMixin, ListView)
```
- Organization-scoped queries
- Multi-field filtering
- Search across details and users
- Related data prefetching for performance

```python
class AuditLogDetailView(LoginRequiredMixin, UserOrganizationMixin, DetailView)
```
- Formatted change display
- Before/after comparison
- Content object retrieval

```python
class AuditLogSummaryView(LoginRequiredMixin, UserOrganizationMixin, TemplateView)
```
- Statistical aggregation
- Date-range configurable
- Activity trend calculation
- User and entity metrics

### Export Functions
- `audit_log_export_csv()`: Export filtered logs to CSV
- `audit_log_export_json()`: Export filtered logs to JSON

### URL Routes

```
/accounting/audit-logs/              → AuditLogListView
/accounting/audit-logs/<id>/         → AuditLogDetailView  
/accounting/audit-logs/summary/      → AuditLogSummaryView
/accounting/audit-logs/export/csv/   → CSV export
/accounting/audit-logs/export/json/  → JSON export
```

### Templates

**audit_log_list.html** (460+ lines)
- Filter form with date, user, action, search
- Responsive table with pagination
- Export buttons
- Dason template styling

**audit_log_detail.html** (350+ lines)
- Tabbed/sectioned layout
- Sidebar with related information
- Change history visualization
- Hash-chain navigation

**audit_log_summary.html** (400+ lines)
- KPI cards
- Chart.js integration for daily activity
- Top users/entities tables
- Period selector

## Security Features

✅ **Organization Scoping**
- Non-superusers see only their organization's logs
- Superusers can see all logs

✅ **Permission Checking**
- LoginRequiredMixin ensures user is authenticated
- UserOrganizationMixin ensures org context
- Can be extended with PermissionRequiredMixin

✅ **Data Integrity**
- Read-only views (no edit/delete capability)
- Hash verification status displayed
- Immutable record indicators

✅ **Audit Trail of Audit Logs**
- Export actions are logged to AuditLog
- All view access can be extended to log views

## UI/UX Consistency with Dason Template

✅ Bootstrap 5 components
✅ Card-based layout
✅ Consistent badge and icon styling
✅ Responsive design (mobile-friendly)
✅ Color-coded action types
✅ Progress bars and metrics
✅ Avatar components for users
✅ Breadcrumb navigation
✅ Consistent spacing and typography

## Performance Optimizations

- `select_related()` for foreign keys (user, organization, content_type)
- `prefetch_related()` for reverse relations
- `db_index=True` on timestamp field
- Composite indexes on (organization, timestamp) and (user, timestamp)
- Pagination to limit query results
- Export limit of 10,000 rows per file

## Sidebar Navigation

The Audit Log is accessible from the left sidebar under **Settings**:
```html
<a href="{% url 'admin:accounting_auditlog_changelist' %}">
    <i data-feather="activity"></i>
    <span>Audit Log</span>
</a>
```

Permission check: `user|has_permission:'accounting_auditlog_view'`

## Future Enhancements

- [ ] Real-time audit log streaming via WebSocket
- [ ] Advanced filtering with saved filter sets
- [ ] Bulk actions on audit logs
- [ ] Anomaly detection alerts
- [ ] Compliance report generation
- [ ] Integration with external audit log storage
- [ ] Full-text search capabilities
- [ ] Audit log retention policies UI

## Testing the Implementation

### Access the views:
1. **List View**: Navigate to `/accounting/audit-logs/`
2. **Detail View**: Click on any log entry or navigate to `/accounting/audit-logs/1/`
3. **Summary**: Navigate to `/accounting/audit-logs/summary/`

### Filter options:
- Use date range picker to filter by date
- Select user to see their activity
- Choose action type to filter by operation
- Use search box for free-text search

### Export:
- Click CSV or JSON buttons to download filtered data
- Filters are preserved in export

## Files Modified/Created

### New Files:
- `accounting/views/audit_log_views.py` (420 lines)
- `accounting/templates/accounting/audit_log_list.html` (460 lines)
- `accounting/templates/accounting/audit_log_detail.html` (350 lines)
- `accounting/templates/accounting/audit_log_summary.html` (400 lines)

### Modified Files:
- `accounting/urls/__init__.py` - Added imports and 5 new routes

### Total Lines Added: ~1,630 lines of production code

## Permissions

To use the Audit Log UI, users need:
- `is_authenticated` (LoginRequiredMixin)
- Optional: `accounting_auditlog_view` permission for RBAC (can be added)

Default behavior: All authenticated users can view audit logs for their organization.

## Integration with Audit Trail Implementation

This UI layer integrates with the existing audit trail system:
- Models: `AuditLog`, `LoginEventLog`
- Signal handlers: Auto-logging of model changes
- Hash-chaining: Immutability verification
- RBAC: Organization-scoped access control

The views query the populated `AuditLog` table and present the data in a user-friendly dashboard format, replacing the Django admin panel interface.
