# Advanced Form Base - Quick Reference Card

## ⚡ Quick Migration (3 Steps)

### 1️⃣ Settings (Already Done ✅)
All configurations added to `dashboard/settings.py` → `ADVANCED_FORM_FEATURES`

### 2️⃣ Update View (Pattern)
```python
from accounting.mixins import AdvancedFormMixin

class YourModelCreateView(AdvancedFormMixin, LoginRequiredMixin, CreateView):
    app_name = 'accounting'
    model_name = 'your_model'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Your Model'
        context['list_url'] = reverse('accounting:your_model_list')
        return context
```

### 3️⃣ Update Template
```django
{% extends 'accounting/_coa_form_base.html' %}

{% block form_content %}
<div class="tab-content">
    <div class="tab-pane fade show active" id="single-entry">
        <form id="your-model-form" method="post" novalidate>
            {% csrf_token %}
            <!-- Fields here -->
            <!-- Use enhanced field pattern -->
        </form>
    </div>
</div>
{% endblock %}
```

---

## 📝 Enhanced Field Templates

### Text Input (Required)
```django
<div class="col-md-6">
    <div class="mb-3">
        <label for="{{ form.name.id_for_label }}" class="form-label required-field">Name</label>
        <input type="text" name="name" id="{{ form.name.id_for_label }}" 
               class="form-control{% if form.name.errors %} is-invalid{% endif %}"
               value="{{ form.name.value|default:'' }}"
               required data-pristine-required-message="Name is required">
        {% if form.name.errors %}<div class="error-message">{{ form.name.errors|first }}</div>{% endif %}
    </div>
</div>
```

### Select Dropdown
```django
<div class="col-md-6">
    <div class="mb-3">
        <label for="{{ form.type.id_for_label }}" class="form-label required-field">Type</label>
        <select name="type" id="{{ form.type.id_for_label }}" 
                class="form-select{% if form.type.errors %} is-invalid{% endif %}"
                required data-pristine-required-message="Type is required">
            <option value="">Select Type</option>
            {% for value, label in form.type.field.choices %}
                <option value="{{ value }}"{% if value == form.type.value %} selected{% endif %}>{{ label }}</option>
            {% endfor %}
        </select>
        {% if form.type.errors %}<div class="error-message">{{ form.type.errors|first }}</div>{% endif %}
    </div>
</div>
```

### Checkbox/Switch
```django
<div class="col-md-6">
    <div class="form-check form-switch mb-3">
        <input class="form-check-input" type="checkbox" name="is_active" 
               id="{{ form.is_active.id_for_label }}"
               {% if form.is_active.value %}checked{% endif %}>
        <label class="form-check-label" for="{{ form.is_active.id_for_label }}">Active</label>
    </div>
</div>
```

---

## 🎨 Form Organization

### Section Header
```django
<div class="row mb-4">
    <div class="col-12">
        <h5 class="text-primary mb-3"><i class="bx bx-info-circle"></i> Basic Information</h5>
    </div>
    <!-- Fields -->
</div>
```

### Form Actions (Bottom)
```django
<div class="row">
    <div class="col-12">
        <hr class="my-4">
        <div class="d-flex justify-content-between align-items-center">
            <a href="{{ list_url }}" class="btn btn-light"><i class="bx bx-x"></i> Cancel</a>
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
```

---

## ⌨️ Built-in Features (Automatic)

✅ **Keyboard Shortcuts:**
- `Ctrl+S` - Save
- `Ctrl+Enter` - Save & New
- `Shift+?` - Show shortcuts
- `Esc` - Close panels

✅ **Validation:**
- Client-side with Pristine.js
- Visual error states
- Auto-focus on errors
- Custom error messages

✅ **Quick Actions Bar:**
- Save button
- Save & New button  
- Shortcuts button
- Back button

✅ **UX Enhancements:**
- Loading indicators
- Smooth transitions
- Toast notifications
- Required field markers

---

## 🎯 Priority Migration Order

**✅ COMPLETED:**
1. Chart of Accounts
2. Account Type

**🔴 HIGH (Do Next):**
3. Currency
4. Tax Type
5. Tax Code
6. Fiscal Year
7. Cost Center
8. Department
9. Journal Type
10. Project

**🟡 MEDIUM (After High):**
11-17. Other accounting forms

---

## 🧪 Testing Checklist

After migrating each form:

- [ ] Form loads without errors
- [ ] Required fields show (*)
- [ ] Submit empty form (validation works)
- [ ] `Ctrl+S` saves
- [ ] `Ctrl+Enter` saves & creates new
- [ ] `Shift+?` shows shortcuts
- [ ] Back button works
- [ ] Errors display properly
- [ ] Success toast appears

---

## 📚 Resources

- **Migration Guide:** `docs/ADVANCED_FORM_MIGRATION_GUIDE.md`
- **Example Form:** `accounting/templates/accounting/account_type_form.html`
- **Example View:** `accounting/views/views_create.py` (AccountTypeCreateView)
- **Base Template:** `accounting/templates/accounting/_coa_form_base.html`
- **Settings:** `dashboard/settings.py` (ADVANCED_FORM_FEATURES)
- **Migration Script:** `python scripts/migrate_forms_to_advanced_base.py --dry-run`

---

## 💡 Pro Tips

1. **Start small**: Migrate Currency form first (simple)
2. **Use Account Type as template**: Copy and adapt
3. **Test immediately**: Don't migrate multiple forms at once
4. **Keep old template**: Rename to `_old` as backup
5. **Check console**: Look for JavaScript errors
6. **Verify settings**: Match model_name exactly with settings key

---

## 🆘 Common Issues

| Issue | Solution |
|-------|----------|
| Shortcuts not working | Check `enable_shortcuts: True` in settings |
| Validation not showing | Add `novalidate` to form, `required` to fields |
| Save & New not working | Button needs `name="save_and_new"` |
| Styling broken | Verify Bootstrap 5 classes |
| Template not found | Check extends `_coa_form_base.html` |

---

**🎉 Happy Migrating! Start with Currency form - it's the easiest!**
