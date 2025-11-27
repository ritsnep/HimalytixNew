# Advanced Form Base Migration Guide

## Overview
This guide helps you migrate existing forms to use the Universal Advanced Form Base system with keyboard shortcuts, pristine validation, and enhanced UX.

---

## Quick Start (3 Steps)

### 1. Update Settings Configuration
Add your form to `dashboard/settings.py` → `ADVANCED_FORM_FEATURES`:

```python
ADVANCED_FORM_FEATURES = {
    'accounting': {
        'your_model_name': {
            'enable_tabs': False,           # Set to True if you want tabs
            'enable_bulk_import': False,    # Set to True for bulk import
            'enable_templates': False,      # Set to True for templates
            'enable_shortcuts': True,       # ✅ Recommended
            'enable_save_and_new': True,    # ✅ Recommended
        },
    },
}
```

### 2. Update View Class
Add `AdvancedFormMixin` to your CreateView and UpdateView:

```python
# Import the mixin
from accounting.mixins import AdvancedFormMixin

# Update CreateView
class YourModelCreateView(AdvancedFormMixin, LoginRequiredMixin, CreateView):
    model = YourModel
    form_class = YourModelForm
    template_name = 'accounting/your_model_form.html'
    
    # Add these configuration attributes
    app_name = 'accounting'
    model_name = 'your_model_name'  # Must match settings key
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Create Your Model'
        context['page_title'] = 'Your Model'
        context['list_url'] = reverse('accounting:your_model_list')
        # ... rest of your context
        return context

# Update UpdateView (same pattern)
class YourModelUpdateView(AdvancedFormMixin, LoginRequiredMixin, UpdateView):
    # Same configuration as CreateView
```

### 3. Update Template
Change template to extend `_coa_form_base.html` and wrap content in tab structure:

```django
{% extends 'accounting/_coa_form_base.html' %}
{% load static %}

{% block title %}Your Model{% endblock %}

{% block form_content %}
<div class="tab-content" id="yourModelTabContent">
    <!-- Single Entry Tab (Default) -->
    <div class="tab-pane fade show active" id="single-entry" role="tabpanel">
        <form id="your-model-form" method="post" novalidate>
            {% csrf_token %}
            
            <!-- Your form fields here -->
            <!-- Use the enhanced field pattern shown below -->
            
            <!-- Form Actions -->
            <div class="row">
                <div class="col-12">
                    <hr class="my-4">
                    <div class="d-flex justify-content-between align-items-center">
                        <a href="{{ list_url }}" class="btn btn-light">
                            <i class="bx bx-x"></i> Cancel
                        </a>
                        <div>
                            <button type="submit" name="save_and_new" class="btn btn-success">
                                <i class="bx bx-save"></i> Save & New
                                <span class="htmx-indicator spinner-border spinner-border-sm ms-1"></span>
                            </button>
                            <button type="submit" class="btn btn-primary">
                                <i class="bx bx-save"></i> Save
                                <span class="htmx-indicator spinner-border spinner-border-sm ms-1"></span>
                            </button>
                        </div>
                    </div>
                    
                    <div class="mt-3 text-muted small">
                        <i class="bx bx-info-circle"></i> 
                        <strong>Quick Tip:</strong> Press <kbd>Ctrl+S</kbd> to save
                    </div>
                </div>
            </div>
        </form>
    </div>
</div>
{% endblock %}

{% block extra_form_js %}
// Your form-specific JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('Your Model Form loaded');
});
{% endblock %}
```

---

## Enhanced Field Patterns

### Text Input (Required)
```django
<div class="col-md-6">
    <div class="mb-3">
        <label for="{{ form.field_name.id_for_label }}" class="form-label required-field">
            Field Label
        </label>
        <input type="text" 
               name="field_name" 
               id="{{ form.field_name.id_for_label }}" 
               class="form-control{% if form.field_name.errors %} is-invalid{% endif %}"
               value="{{ form.field_name.value|default:'' }}"
               placeholder="Enter value"
               required
               data-pristine-required-message="This field is required"
               autofocus>
        {% if form.field_name.errors %}
        <div class="error-message">{{ form.field_name.errors|first }}</div>
        {% endif %}
        <small class="text-muted">Helper text (optional)</small>
    </div>
</div>
```

### Select Dropdown (Required)
```django
<div class="col-md-6">
    <div class="mb-3">
        <label for="{{ form.field_name.id_for_label }}" class="form-label required-field">
            Field Label
        </label>
        <select name="field_name" 
                id="{{ form.field_name.id_for_label }}" 
                class="form-select{% if form.field_name.errors %} is-invalid{% endif %}"
                required
                data-pristine-required-message="Please select an option">
            <option value="">Select Option</option>
            {% if form.field_name.field.choices %}
                {% for value, label in form.field_name.field.choices %}
                    <option value="{{ value }}"{% if value == form.field_name.value %} selected{% endif %}>
                        {{ label }}
                    </option>
                {% endfor %}
            {% endif %}
        </select>
        {% if form.field_name.errors %}
        <div class="error-message">{{ form.field_name.errors|first }}</div>
        {% endif %}
    </div>
</div>
```

### Number Input
```django
<div class="col-md-6">
    <div class="mb-3">
        <label for="{{ form.field_name.id_for_label }}" class="form-label">
            Field Label
        </label>
        <input type="number" 
               name="field_name" 
               id="{{ form.field_name.id_for_label }}" 
               class="form-control{% if form.field_name.errors %} is-invalid{% endif %}"
               value="{{ form.field_name.value|default:'' }}"
               min="0"
               step="0.01">
        {% if form.field_name.errors %}
        <div class="error-message">{{ form.field_name.errors|first }}</div>
        {% endif %}
    </div>
</div>
```

### Checkbox/Switch
```django
<div class="col-md-6">
    <div class="form-check form-switch mb-3">
        <input class="form-check-input" 
               type="checkbox" 
               name="field_name" 
               id="{{ form.field_name.id_for_label }}"
               {% if form.field_name.value %}checked{% endif %}>
        <label class="form-check-label" for="{{ form.field_name.id_for_label }}">
            Field Label
        </label>
        {% if form.field_name.errors %}
        <div class="error-message">{{ form.field_name.errors|first }}</div>
        {% endif %}
        <small class="text-muted d-block">Helper text</small>
    </div>
</div>
```

### Textarea
```django
<div class="col-12">
    <div class="mb-3">
        <label for="{{ form.field_name.id_for_label }}" class="form-label">
            Field Label
        </label>
        <textarea name="field_name" 
                  id="{{ form.field_name.id_for_label }}" 
                  class="form-control{% if form.field_name.errors %} is-invalid{% endif %}"
                  rows="3"
                  placeholder="Enter description">{{ form.field_name.value|default:'' }}</textarea>
        {% if form.field_name.errors %}
        <div class="error-message">{{ form.field_name.errors|first }}</div>
        {% endif %}
    </div>
</div>
```

---

## Form Organization Best Practices

### Section Headers
```django
<div class="row mb-4">
    <div class="col-12">
        <h5 class="text-primary mb-3">
            <i class="bx bx-info-circle"></i> Section Name
        </h5>
    </div>
    
    <!-- Fields go here -->
</div>
```

### Common Icons
- `bx-info-circle` - Basic Information
- `bx-category` - Classification
- `bx-bar-chart` - Financial Data
- `bx-code-alt` - Code Configuration
- `bx-cog` - Options/Settings
- `bx-user` - User Information
- `bx-calendar` - Date/Time
- `bx-dollar-circle` - Financial

---

## Feature Configuration Guide

### Minimal (Shortcuts Only)
```python
'your_model': {
    'enable_shortcuts': True,
    'enable_save_and_new': True,
}
```
**Best for:** Simple forms with few fields

### Standard (No Tabs)
```python
'your_model': {
    'enable_tabs': False,
    'enable_bulk_import': False,
    'enable_templates': False,
    'enable_shortcuts': True,
    'enable_save_and_new': True,
}
```
**Best for:** Most forms (like Account Types, Currency, etc.)

### Advanced (With Tabs)
```python
'your_model': {
    'enable_tabs': True,
    'enable_bulk_import': True,
    'enable_templates': True,
    'enable_shortcuts': True,
    'enable_save_and_new': True,
}
```
**Best for:** Complex forms like Chart of Accounts, Journal Entry

---

## Forms to Migrate (Priority Order)

### High Priority (Frequently Used)
1. ✅ Chart of Accounts - **DONE**
2. ✅ Account Type - **DONE**
3. ⏳ Currency
4. ⏳ Tax Type
5. ⏳ Tax Code
6. ⏳ Fiscal Year
7. ⏳ Cost Center
8. ⏳ Department
9. ⏳ Journal Type
10. ⏳ Project

### Medium Priority
11. ⏳ Tax Authority
12. ⏳ Currency Exchange Rate
13. ⏳ Accounting Period
14. ⏳ Voucher Mode Config
15. ⏳ Voucher Mode Default
16. ⏳ Voucher UDF Config
17. ⏳ General Ledger

### Low Priority (Complex/Special)
18. ⏳ Journal Entry (has wizard)
19. ⏳ Voucher Entry (has wizard)

---

## Testing Checklist

After migrating each form, test:

- [ ] Form loads without errors
- [ ] Required fields show asterisk (*)
- [ ] Validation works (submit empty form)
- [ ] Save button works (Ctrl+S)
- [ ] Save & New button works (Ctrl+Enter)
- [ ] Shortcuts panel opens (Shift+?)
- [ ] Back button navigates correctly
- [ ] Error messages display properly
- [ ] Success message appears after save
- [ ] Form resets after Save & New

---

## Troubleshooting

### Issue: Shortcuts not working
**Solution:** Check that `enable_shortcuts: True` in settings

### Issue: Validation not showing
**Solution:** Ensure form has `novalidate` attribute and fields have `required`

### Issue: Save & New not working
**Solution:** Check button has `name="save_and_new"` attribute

### Issue: Quick Actions bar not visible
**Solution:** Verify template extends `_coa_form_base.html`

### Issue: Form not styled properly
**Solution:** Check Bootstrap 5 classes are applied correctly

---

## Next Steps

1. **Start with Currency form** (simple, frequently used)
2. **Use Account Type form as reference** (recently completed)
3. **Migrate forms one at a time** (test thoroughly)
4. **Update documentation** as you go

---

## Support

- Review: `accounting/templates/accounting/account_type_form.html`
- Review: `accounting/views/views_create.py` (AccountTypeCreateView)
- Review: `dashboard/settings.py` (ADVANCED_FORM_FEATURES)
- Base Template: `accounting/templates/accounting/_coa_form_base.html`
