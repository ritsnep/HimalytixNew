# Voucher Entry System - Quick Reference Guide

## URL Patterns

| Action | URL Pattern | View | Permission Required |
|--------|-------------|------|---------------------|
| List all vouchers | `/accounting/vouchers/` | VoucherListView | view |
| Create new voucher | `/accounting/vouchers/new/` | VoucherCreateView | add |
| Create with config | `/accounting/vouchers/new/<config_id>/` | VoucherCreateView | add |
| View voucher details | `/accounting/vouchers/<pk>/` | VoucherDetailView | view |
| Edit voucher | `/accounting/vouchers/<pk>/edit/` | VoucherUpdateView | change |
| Delete voucher | `/accounting/vouchers/<pk>/delete/` | VoucherDeleteView | delete |
| Duplicate voucher | `/accounting/vouchers/<pk>/duplicate/` | VoucherDuplicateView | add |
| Post voucher | `/accounting/vouchers/<pk>/post/` | VoucherPostView | add |

## URL Names (for use in templates)

```django
{% url 'accounting:voucher_list' %}
{% url 'accounting:voucher_create' %}
{% url 'accounting:voucher_detail' pk=voucher.pk %}
{% url 'accounting:voucher_edit' pk=voucher.pk %}
{% url 'accounting:voucher_delete' pk=voucher.pk %}
{% url 'accounting:voucher_duplicate' pk=voucher.pk %}
{% url 'accounting:voucher_post' pk=voucher.pk %}
```

## Status Flow

```
draft → awaiting_approval → approved → posted
  ↓                                      ↓
delete                                reversed
```

### Status Permissions:
- **draft**: Can edit, delete, post, duplicate
- **awaiting_approval**: Can view, approve/reject
- **approved**: Can view, post
- **posted**: Can view, reverse (if permitted)
- **reversed**: Can view only

## Filter Parameters

### List View Filters:
```
?search=<keyword>              # Search in number, reference, description
?status=<status_code>          # Filter by status
?journal_type=<type_id>        # Filter by journal type
?start_date=<YYYY-MM-DD>       # Filter from date
?end_date=<YYYY-MM-DD>         # Filter to date
?page=<number>                 # Pagination
```

### Example:
```
/accounting/vouchers/?status=draft&journal_type=1&start_date=2025-10-01
```

## Template Blocks

### voucher_list.html
- Displays all vouchers with filters
- Pagination enabled (25 per page)
- Search across number, reference, description
- Status badges with color coding

### voucher_detail.html
- Read-only voucher display
- Shows all lines with totals
- Balance indicator
- Audit trail
- Action buttons

### voucher_form.html
- Dynamic form rendering
- Used for both create and edit
- Real-time total calculation
- Add/remove line items

### voucher_confirm_delete.html
- Confirmation page
- Shows voucher summary
- Delete/Cancel options

## Form Data Structure

### Header Data (POST):
```python
{
    'header-journal_date': '2025-10-28',
    'header-journal_type': 1,
    'header-period': 1,
    'header-reference': 'REF-001',
    'header-description': 'Voucher description',
}
```

### Lines Data (POST):
```python
{
    'lines-TOTAL_FORMS': '3',
    'lines-INITIAL_FORMS': '0',
    'lines-0-account': 1,
    'lines-0-description': 'Line 1',
    'lines-0-debit_amount': '1000.00',
    'lines-0-credit_amount': '0.00',
    'lines-1-account': 2,
    'lines-1-description': 'Line 2',
    'lines-1-debit_amount': '0.00',
    'lines-1-credit_amount': '1000.00',
}
```

## Python Usage Examples

### Create Voucher Programmatically:
```python
from accounting.services.create_voucher import create_voucher

journal = create_voucher(
    user=request.user,
    config_id=1,
    header_data={
        'journal_date': '2025-10-28',
        'journal_type_id': 1,
        'period_id': 1,
        'reference': 'REF-001',
        'description': 'Test voucher',
    },
    lines_data=[
        {
            'account_id': 1,
            'description': 'Debit line',
            'debit_amount': 1000.00,
            'credit_amount': 0.00,
        },
        {
            'account_id': 2,
            'description': 'Credit line',
            'debit_amount': 0.00,
            'credit_amount': 1000.00,
        },
    ]
)
```

### Post Voucher:
```python
from accounting.services.post_journal import post_journal

post_journal(journal, user=request.user)
```

### Validate Voucher:
```python
from accounting.validation import JournalValidationService

validator = JournalValidationService(organization)
errors = validator.validate_journal_entry(header_data, lines_data)
```

## Permission Checks in Templates

```django
{% if perms.accounting.add_journal %}
    <a href="{% url 'accounting:voucher_create' %}">Create New</a>
{% endif %}

{% if perms.accounting.change_journal and voucher.status == 'draft' %}
    <a href="{% url 'accounting:voucher_edit' pk=voucher.pk %}">Edit</a>
{% endif %}

{% if perms.accounting.delete_journal and voucher.status == 'draft' %}
    <a href="{% url 'accounting:voucher_delete' pk=voucher.pk %}">Delete</a>
{% endif %}
```

## JavaScript Integration

### HTMX Support:
```html
<form hx-post="{% url 'accounting:voucher_create' %}"
      hx-target="#result"
      hx-swap="innerHTML">
    <!-- form fields -->
</form>
```

### AJAX Submit:
```javascript
$.ajax({
    url: '{% url "accounting:voucher_create" %}',
    method: 'POST',
    data: formData,
    success: function(response) {
        window.location.href = response.redirect_url;
    },
    error: function(xhr) {
        displayErrors(xhr.responseJSON.errors);
    }
});
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Voucher not found" | Invalid PK or org mismatch | Check voucher ID and organization |
| "Cannot edit posted voucher" | Trying to edit non-draft | Only draft vouchers editable |
| "Debit/Credit imbalance" | Totals don't match | Check line amounts |
| "Invalid period" | Period closed or invalid | Select open period |
| "Permission denied" | Missing permission | Check user permissions |

## Keyboard Shortcuts (Planned)

| Key | Action |
|-----|--------|
| Ctrl+N | New voucher |
| Ctrl+S | Save voucher |
| Ctrl+E | Edit mode |
| Ctrl+D | Duplicate |
| Esc | Cancel/Close |
| Tab | Next field |
| Shift+Tab | Previous field |

## API Endpoints (REST)

If REST API is needed:
```python
GET    /api/v1/vouchers/                 # List vouchers
POST   /api/v1/vouchers/                 # Create voucher
GET    /api/v1/vouchers/<pk>/            # Get voucher
PUT    /api/v1/vouchers/<pk>/            # Update voucher
DELETE /api/v1/vouchers/<pk>/            # Delete voucher
POST   /api/v1/vouchers/<pk>/post/       # Post voucher
POST   /api/v1/vouchers/<pk>/duplicate/  # Duplicate voucher
```

## Troubleshooting

### Issue: Forms not displaying
**Solution:** Check that voucher configuration exists and is active

### Issue: Validation errors not showing
**Solution:** Check form error handling in template

### Issue: Permission denied
**Solution:** Verify user has required permissions in Django admin

### Issue: Duplicate key error
**Solution:** Check journal_number generation and uniqueness

### Issue: Lines not saving
**Solution:** Verify formset management form is included

## Best Practices

1. **Always validate before posting**
2. **Use transactions for atomic operations**
3. **Check permissions before showing action buttons**
4. **Log all critical operations**
5. **Display user-friendly error messages**
6. **Implement proper error handling**
7. **Test with different user roles**
8. **Keep audit trail complete**

## Configuration Checklist

- [ ] Voucher mode configuration created
- [ ] Journal types configured
- [ ] Accounting periods set up
- [ ] Chart of accounts populated
- [ ] User permissions assigned
- [ ] Templates customized (if needed)
- [ ] Navigation menu updated
- [ ] Test data created
- [ ] User training completed
- [ ] Documentation reviewed

---
**Version:** 1.0
**Last Updated:** October 28, 2025
