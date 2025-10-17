# Phase 1 Quick Reference Guide

## 📚 Core Components

### BaseVoucherView
```python
from accounting.views.base_voucher_view import BaseVoucherView

class YourView(BaseVoucherView):
    template_name = 'your_template.html'
    form_class = JournalForm
    formset_class = JournalLineFormSet
```

**Key Methods**:
- `get_organization()` - Current organization
- `get_context_data()` - Common context
- `render_to_response()` - HTML/HTMX response
- `json_response()` - JSON response
- `save_with_audit()` - Save with logging

---

### VoucherFormFactory
```python
from accounting.forms.form_factory import VoucherFormFactory

# Create forms
journal_form = VoucherFormFactory.get_journal_form(organization)
line_formset = VoucherFormFactory.get_journal_line_formset(organization)

# With data
journal_form = VoucherFormFactory.get_journal_form(
    organization, 
    data=request.POST, 
    files=request.FILES
)

# Create blank line for HTMX
blank_line = VoucherFormFactory.create_blank_line_form(org, form_index=5)

# Validate
is_valid, errors = VoucherFormFactory.validate_forms(journal_form, line_formset)
```

---

### JournalForm
```python
from accounting.forms.journal_form import JournalForm

form = JournalForm(organization=org, data=request.POST)
if form.is_valid():
    journal = form.save()
```

**Validation**:
- `clean_journal_date()` - Date in open period
- `clean_period()` - Period is open
- `clean_currency_code()` - Currency active
- `clean_exchange_rate()` - Exchange rate > 0
- `clean()` - Cross-field validation

---

### JournalLineForm
```python
from accounting.forms.journal_line_form import JournalLineForm, JournalLineFormSet

line_form = JournalLineForm(organization=org, data=request.POST)
formset = JournalLineFormSet(organization=org, instance=journal)
```

**Validation**:
- Exactly ONE of debit or credit (not both, not neither)
- Amounts non-negative
- Tax rate 0-100%
- Exchange rate > 0
- Auto-calculates tax amount

---

### Formsets
```python
from accounting.forms.formsets import JournalLineFormSet

formset = JournalLineFormSet(organization=org, instance=journal, data=request.POST)
if formset.is_valid():
    formset.save()
    
# Get totals
totals = formset.get_totals()
# {'total_debit': Decimal(), 'total_credit': Decimal(), 'is_balanced': bool}

# Get non-deleted forms
active_lines = formset.get_non_deleted_forms()
```

---

## 📋 Form Fields

### Journal Fields
```
journal_type    → ForeignKey (Required)
period          → ForeignKey (Required)
journal_date    → DateInput (Required)
reference       → TextInput (Optional)
description     → Textarea (Optional)
currency_code   → Select (Required)
exchange_rate   → NumberInput (Default: 1.0)
status          → Select (Required)
```

### Line Fields
```
account         → Select (Required)
description     → TextInput (Optional)
debit_amount    → Number (Min: 0)
credit_amount   → Number (Min: 0)
currency_code   → Select
exchange_rate   → Number
department      → Select (Optional)
project         → Select (Optional)
cost_center     → Select (Optional)
tax_code        → Select (Optional)
tax_rate        → Number (0-100%)
tax_amount      → Number (Auto-calculated)
memo            → TextInput (Optional)
udf_data        → JSONField
```

---

## 🔗 URL Patterns

```python
# In urls.py
from . import urls_voucher

urlpatterns = [
    path('journal/', include(urls_voucher)),
]
```

**Available URLs**:
```
/journal/journals/                          → List
/journal/journals/create/                   → Create
/journal/journals/create/<type>/            → Create (typed)
/journal/journals/<id>/                     → Detail
/journal/journals/<id>/edit/                → Edit
/journal/journals/<id>/post/                → Post
/journal/journals/htmx/<action>/            → HTMX
```

---

## 🎨 Templates

### Include Base Template
```django
{% extends 'accounting/base_voucher.html' %}

{% block content %}
  <!-- Your custom content -->
{% endblock %}
```

### Use Factory for Forms
```django
{% load static %}

<form method="post">
  {% csrf_token %}
  
  <!-- Journal fields -->
  <div class="form-group">
    {{ journal_form.journal_type }}
  </div>
  
  <!-- Lines formset -->
  {{ line_formset.management_form }}
  {% for form in line_formset %}
    {{ form }}
  {% endfor %}
  
  <button type="submit">Save</button>
</form>
```

---

## 🛠️ Common Tasks

### Create a New Journal
```python
from accounting.forms.form_factory import VoucherFormFactory
from accounting.models import Journal

# Get form
org = request.user.get_active_organization()
form = VoucherFormFactory.get_journal_form(org, data=request.POST)

# Save
if form.is_valid():
    journal = form.save(commit=False)
    journal.created_by = request.user
    journal.save()
```

### Create with Lines
```python
from accounting.forms.form_factory import VoucherFormFactory

# Get formset
formset = VoucherFormFactory.get_journal_line_formset(
    org, 
    instance=journal, 
    data=request.POST
)

# Validate and save
if formset.is_valid():
    formset.save()
```

### Add HTMX Line
```python
# In view
def handle_add_line(request):
    form_count = request.GET.get('form_count', 0)
    blank_form = VoucherFormFactory.create_blank_line_form(org, form_count)
    return render(request, 'partials/line_form.html', {'form': blank_form})

# In template
<button hx-get="{% url 'add_line' %}" 
        hx-target="#lines"
        hx-swap="beforeend">
  Add Line
</button>
```

### Handle Validation Errors
```python
if not form.is_valid():
    errors = {
        'journal': form.errors,
        'lines': [f.errors for f in formset.forms]
    }
    return render(request, 'error.html', {'errors': errors})
```

---

## 🔐 Security Features

### Organization Filtering
```python
# Automatic - already included
def get_queryset(self):
    # Filtered by organization
    return Journal.objects.filter(organization=self.get_organization())
```

### Audit Logging
```python
# Automatic - already included
self.save_with_audit(journal, lines_data, action='create')
# Creates audit log entry with user, IP, timestamp
```

### CSRF Protection
```django
<!-- In all forms -->
{% csrf_token %}
```

### Transaction Safety
```python
# Automatic - already included
with transaction.atomic():
    journal.save()
    formset.save()
    # Rolls back if error
```

---

## 📊 Error Handling

### Form Errors
```python
if not form.is_valid():
    for field, errors in form.errors.items():
        for error in errors:
            print(f"{field}: {error}")
```

### Formset Errors
```python
if not formset.is_valid():
    for form in formset.forms:
        if form.errors:
            print(form.errors)
    if formset.non_form_errors():
        print(formset.non_form_errors())
```

### Check Balance
```python
totals = formset.get_totals()
if not totals['is_balanced']:
    print(f"Out of balance: {totals['balance']}")
```

---

## 🧪 Testing

### Test Form Creation
```python
from accounting.forms.journal_form import JournalForm

form = JournalForm(
    organization=org,
    data={
        'journal_type': jt.id,
        'period': period.id,
        'journal_date': '2025-10-16',
        'currency_code': 'USD',
    }
)
assert form.is_valid()
```

### Test Validation
```python
form = JournalForm(
    organization=org,
    data={'journal_date': '2025-12-25'}  # Not in period
)
assert not form.is_valid()
assert 'journal_date' in form.errors
```

### Test Formset
```python
formset = JournalLineFormSet(
    organization=org,
    instance=journal,
    data=formset_data
)
if formset.is_valid():
    formset.save()
```

---

## 📖 Documentation Files

- `accounting/PHASE_1_IMPLEMENTATION.md` - Complete implementation guide
- `accounting/PHASE_1_COMPLETION_REPORT.md` - Full completion report
- Docstrings in all Python files
- Type hints throughout

---

## 🚀 Next Steps (Phase 2)

1. Create concrete view implementations
2. Add HTMX handlers
3. Create template partials
4. Add JavaScript for client-side features
5. Write test suite
6. Add API endpoints

---

## 💡 Tips & Tricks

### Always pass organization
```python
# ✅ Correct
form = VoucherFormFactory.get_journal_form(organization)

# ❌ Wrong - no organization
form = JournalForm()
```

### Use factory for consistency
```python
# ✅ Good - uses factory
form = VoucherFormFactory.get_journal_form(org)

# ⚠️ Not recommended - avoid direct instantiation
form = JournalForm(organization=org)
```

### Check HTMX status
```python
# Detect HTMX request
if self.is_htmx_request():
    # Return fragment template
    return self.render_to_response(context)
else:
    # Return full page
    return self.render_to_response(context)
```

### Use formset get_totals()
```python
# Calculate totals
totals = formset.get_totals()
print(f"Debit: {totals['total_debit']}")
print(f"Credit: {totals['total_credit']}")
print(f"Balanced: {totals['is_balanced']}")
```

---

## ❓ FAQ

**Q: Do I need to pass organization to every form?**
A: Yes, always pass organization to ensure data isolation.

**Q: Can I edit a posted journal?**
A: No, the form prevents it. Check `clean()` method.

**Q: How are line numbers assigned?**
A: Auto-assigned in multiples of 10 (10, 20, 30...) for easy insertion.

**Q: Is debit/credit validation done in form or formset?**
A: Both - line-level in form, journal-level in formset.

**Q: How do I add HTMX lines?**
A: Use `VoucherFormFactory.create_blank_line_form()` in HTMX handler.

---

## 📞 Support

For questions:
1. Check the docstrings in the code
2. Read PHASE_1_IMPLEMENTATION.md
3. Review type hints for expected types
4. Look at example usage in docstrings

---

**Version**: 1.0.0
**Date**: October 16, 2025
**Status**: Production Ready
