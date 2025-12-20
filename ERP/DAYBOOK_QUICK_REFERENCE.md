# Daybook Report - Quick Reference Guide

## Access the Daybook Report

### Via Navigation Menu
1. Log in to the ERP system
2. Click **Accounting** in the left sidebar
3. Expand **Financial Reports**
4. Click **Daybook** (first item with calendar icon)

### Direct URL
```
/accounting/advanced-reports/daybook/
```

## Filter Options

### Date Range (Required)
- **Start Date**: Beginning of the period
- **End Date**: End of the period
- Format: YYYY-MM-DD

### Status Filter
- All Statuses
- Draft
- Awaiting Approval
- Approved
- Posted
- Rejected

### Journal Type
- All Types
- Or select specific journal type (GJ, PY, etc.)

### Account Filter
- All Accounts
- Or select specific account by code and name

### Voucher Number Search
- Enter partial or full voucher number
- Case-insensitive search

## Features

### Statistics Dashboard
- **Total Debits**: Sum of all debit amounts
- **Total Credits**: Sum of all credit amounts
- **Balance**: Difference (should be 0 for balanced entries)
- **Transactions**: Count of journal entries

### Transaction Table
Displays:
- Date
- Voucher # (clickable link to detail)
- Journal Type
- Account Code & Name
- Description
- Debit Amount
- Credit Amount
- Status Badge

### Export Options
- **CSV**: Download as comma-separated values
- **Excel**: Download as .xlsx spreadsheet
- **PDF**: Download as PDF document
- **Print**: Browser print dialog

## Quick Tips

1. **Default Date Range**: Last 30 days
2. **Clear Filters**: Click "Clear Filters" button to reset
3. **Drill Down**: Click voucher number to view journal details
4. **Multiple Filters**: Combine filters for precise results
5. **Export**: All filters apply to exports

## Keyboard Shortcuts

- `Ctrl+P`: Print report
- `Tab`: Navigate between filter fields
- `Enter`: Submit form (when focused on input)

## Common Use Cases

### Daily Transaction Review
```
Filters: Today's date for both start and end
Status: All
```

### Posted Transactions Only
```
Filters: Date range + Status = Posted
```

### Account-Specific Report
```
Filters: Date range + Select specific account
```

### Journal Type Analysis
```
Filters: Date range + Journal Type selection
```

## Troubleshooting

### No Results Showing
- Check date range includes transactions
- Verify filters are not too restrictive
- Ensure organization has data for period

### Export Not Working
- Verify date range is selected
- Check browser popup blocker settings
- Try different export format

### Slow Loading
- Reduce date range
- Apply more specific filters
- Contact system administrator

## Report Interpretation

### Balanced Entries
- Debit total = Credit total
- Balance = 0
- Indicates properly posted entries

### Unbalanced Entries
- May include draft entries
- Filter by "Draft" status to review
- Should not appear in "Posted" status

## Contact Support

For issues or questions:
- Email: support@himalytix.com
- Documentation: /docs/accounting/daybook
- Training: Available in Help menu

---

**Last Updated**: December 19, 2025
**Version**: 1.0
