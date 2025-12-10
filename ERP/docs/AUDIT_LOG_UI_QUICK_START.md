# Audit Log UI - Quick Start Guide

## Accessing the Audit Log

### Method 1: From Sidebar
1. Look for **Settings** section in the left sidebar
2. Click **Audit Log** (with activity icon 📊)
3. You'll be taken to the audit log list view

### Method 2: Direct URL
- List: `http://localhost:8000/accounting/audit-logs/`
- Summary: `http://localhost:8000/accounting/audit-logs/summary/`
- Detail: `http://localhost:8000/accounting/audit-logs/[id]/`

## Understanding the Audit Log List

### Filter Controls
```
┌─────────────────────────────────────────────────┐
│ From Date │ To Date │ User │ Action │ Search    │
│ [picker]  │ [picker] │ [▼]  │ [▼]    │ [input]   │
│                [Filter] [Reset]                  │
└─────────────────────────────────────────────────┘
```

**From Date/To Date**: Select date range for audit logs
**User**: Filter by who made the change
**Action**: Filter by type (Create, Update, Delete, etc.)
**Search**: Find logs by details or user name

### Table Columns

| Column | Meaning |
|--------|---------|
| **Timestamp** | Date and time of change |
| **User** | Who made the change (with IP if available) |
| **Action** | Type of change (color-coded badge) |
| **Model / Entity** | What was changed (entity type and ID) |
| **Details** | Additional information about the change |
| **Status** | Sealed (locked/immutable) or Active |
| **Actions** | View details button |

### Color Codes for Actions

- 🟢 **Create** - New record added
- 🔵 **Update** - Record modified
- 🔴 **Delete** - Record removed
- 🔷 **Other** - Approve, Reject, Post, etc.

## Viewing Detailed Changes

1. Click the **👁 eye icon** in the Actions column
2. You'll see:
   - **Event Information**: What happened and when
   - **Changes Section**: Before and after values side-by-side
   - **User Information**: Who made the change
   - **Network Info**: IP address
   - **Integrity Status**: Whether the record is sealed
   - **Related Links**: Quick access to similar changes

Example Change Display:
```
Field: Amount
Old Value: 1000.00
New Value: 1500.00
```

## Summary Dashboard

**Navigate**: Click **Summary** button or go to `/accounting/audit-logs/summary/`

### What You'll See:

**1. Quick Stats Cards**
- Total audit logs
- Number of active users
- Number of modified models
- Selected date range (last 7/30/60/90 days)

**2. Daily Activity Chart**
- Line graph showing audit events over time
- Hover to see exact daily counts
- Shows trends and patterns

**3. Action Breakdown**
- Pie chart showing distribution of actions
- Create vs Update vs Delete ratio
- Percentage of each action type

**4. Most Active Users**
- Ranked list of users who made the most changes
- Progress bars showing relative activity
- Click user name to view their audit logs

**5. Most Modified Models**
- Ranked list of entities that changed most
- Journal Entry, Sales Invoice, etc.
- Click to filter logs for that model

## Export Data

### CSV Export
1. Click **CSV** button (top-right)
2. File downloads as `audit-log-[date].csv`
3. Filters are applied - only filtered logs are exported
4. Open in Excel, Google Sheets, etc.

### JSON Export
1. Click **JSON** button
2. File downloads as `audit-log-[date].json`
3. Useful for data analysis or API consumption
4. Contains full change details and metadata

### Columns Exported

```csv
Timestamp, User, Organization, Action, Model, Object ID, Details, IP Address, Changes, Immutable
2025-12-11T15:30:45, john.smith, ACME Corp, Update, Journal, 123, Modified amount, 192.168.1.1, {...}, No
```

## Common Tasks

### Find what changed for a specific user
1. Go to Audit Log list
2. Select user from dropdown
3. Click Filter
4. See all their changes

### Track changes to a specific journal entry
1. Go to Audit Log list
2. Filter by date range (when you remember it was changed)
3. Or search for details
4. Look for model "Journal" with the object ID

### View all deletions in a date range
1. Go to Audit Log list
2. Select date range
3. Choose "Delete" from Action dropdown
4. Click Filter
5. See all deletions in that period

### Check if data was modified after posting
1. View the detail of the entry you're concerned about
2. Look at timestamp
3. Check "Sealed" status - if sealed, it cannot be changed
4. Review related logs for any post-seal changes (there shouldn't be any)

## Understanding Seal Status

### 🔒 Sealed (Immutable)
- Record cannot be modified
- Locked with hash-chain verification
- For compliance/audit purposes
- Hash values prevent tampering

### 🔓 Active
- Record is still being tracked
- Can potentially be modified
- Changes will be recorded
- Not yet sealed/archived

## Privacy & Permissions

✅ **Your Organization**: You only see logs for your organization
✅ **IP Addresses**: Shown to track access patterns
✅ **User Names**: Visible for accountability
✅ **Sensitive Data**: Changes to amounts, descriptions visible for authorized users

## Troubleshooting

### No audit logs showing
- Check date range - might be outside the filter
- Ensure you have permission to view
- Logs only exist for actions that occurred after implementation

### Missing user details
- User may have been deleted but logs remain
- Shows "Unknown" or user ID instead

### Can't see another organization's logs
- This is by design - multi-tenant isolation
- Contact admin if you need cross-org audit access

### Export file too large
- Limited to 10,000 rows per export
- Use date filters to split exports
- Or export as JSON for smaller file size

## Tips & Best Practices

1. **Regular Reviews**: Check Summary weekly to spot unusual activity
2. **Use Date Ranges**: Faster queries with narrow date ranges
3. **Save Exports**: Keep CSV exports for compliance documentation
4. **Monitor Users**: Track new user activity in first days
5. **Check Post-Dated Changes**: Review changes made AFTER posting
6. **Verify Seals**: Confirm important records are sealed/immutable
7. **Search Details**: Use narration field to find specific transactions

## Support

For issues with the Audit Log interface:
1. Check system logs at `/admin/` (Django admin)
2. Contact your system administrator
3. Report bugs with steps to reproduce
