# Journal Entry UI Standardization Plan

## Executive Summary
This document outlines the plan to standardize the journal entry UI with Dason template conventions while preserving the schema-driven functionality and modern UX enhancements.

## Current State Analysis

### Template Structure
- **Base Template**: `partials/base.html` (Dason admin template)
- **Current Page**: `accounting/templates/accounting/journal_entry.html`
- **Content Block**: Wrapped in `page-content > container-fluid`
- **CSS Files**: 
  - `voucher_entry.css` (custom styles)
  - `voucher_entry_glass.css` (iOS-style glassmorphism - may conflict)

### Dason Template Conventions

#### Layout Structure
```html
{% extends "partials/base.html" %}

{% block content %}
<div class="page-content">
    <div class="container-fluid">
        <!-- Breadcrumbs -->
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">...</ol>
        </nav>
        
        <!-- Page Header -->
        <div class="row">
            <div class="col-12">
                <div class="page-title-box d-flex align-items-center justify-content-between">
                    <h4 class="mb-0">Page Title</h4>
                    <div class="page-title-right">
                        <!-- Actions -->
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title">Section Title</h5>
                    </div>
                    <div class="card-body">
                        <!-- Content -->
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock content %}
```

#### Bootstrap/Dason CSS Classes

**Cards:**
- `.card` - main card container
- `.card-header` - header section
- `.card-body` - main content
- `.card-footer` - footer section
- `.card-title` - title in header

**Buttons:**
- `.btn` - base button class
- `.btn-primary` - primary action (Dason blue: #1c84ee)
- `.btn-success` - success action (green: #34c38f)
- `.btn-danger` - delete/cancel (red: #f46a6a)
- `.btn-warning` - edit/warning (yellow: #f1b44c)
- `.btn-info` - info action (cyan: #50a5f1)
- `.btn-secondary` - secondary action (gray: #74788d)
- `.btn-sm` / `.btn-lg` - size variants

**Forms:**
- `.form-control` - input fields
- `.form-select` - select dropdowns
- `.form-label` - field labels
- `.form-group` - field wrapper (older Bootstrap, still used)
- `.mb-3` - margin bottom 3 (spacing between fields)
- `.input-group` - grouped inputs (prefix/suffix)

**Tables:**
- `.table` - base table
- `.table-bordered` - bordered cells
- `.table-striped` - striped rows
- `.table-hover` - hover effect
- `.table-responsive` - responsive wrapper

**Utilities:**
- `.text-muted` - muted text color
- `.badge` - badges (status indicators)
- `.badge-success`, `.badge-danger`, `.badge-warning`, etc.
- `.d-flex` - flexbox container
- `.align-items-center` - vertical center
- `.justify-content-between` - space between
- `.mb-0`, `.mb-2`, `.mb-3` - margin bottom
- `.mt-2`, `.mt-3` - margin top
- `.p-2`, `.p-3` - padding

**Colors:**
- Primary: `#1c84ee` (Dason blue)
- Success: `#34c38f` (green)
- Danger: `#f46a6a` (red)
- Warning: `#f1b44c` (yellow)
- Info: `#50a5f1` (cyan)
- Secondary: `#74788d` (gray)
- Dark: `#2b3940`
- Light: `#f8f9fa`

**Dark Mode:**
- Dason supports `body[data-layout-mode=dark]`
- Forms: `.form-control` auto-adapts
- Cards: auto-adapts background/borders
- Custom CSS should use dark mode selectors

## Gap Analysis

### What's Working
✅ Schema loads correctly from Forms Designer configuration  
✅ Dynamic field rendering from `headerFieldDefs` and `configLineDefs`  
✅ Config selection modal with smooth UX  
✅ JavaScript is schema-driven (no hardcoded Sales/Purchase)  
✅ Template extends proper base structure  

### What Needs Standardization

#### 1. **Template Structure** (Priority: HIGH)
**Current Issues:**
- No breadcrumbs
- No page title box with actions
- Missing standard card structure around #app container
- Modal uses inline styles instead of Dason classes

**Required Changes:**
- Add breadcrumbs navigation
- Add page-title-box with title and action buttons
- Wrap main content in `.card` structure
- Update modal to use Bootstrap 5 classes properly

#### 2. **CSS Files** (Priority: HIGH)
**Current Issues:**
- `voucher_entry_glass.css` uses custom CSS variables that may conflict
- Glassmorphism effects (backdrop-filter) may not match Dason aesthetic
- Inline styles in template for modal items

**Required Changes:**
- Review and merge essential styles from `voucher_entry_glass.css` into `voucher_entry.css`
- Remove or namespace conflicting CSS variables
- Replace inline styles with Dason utility classes
- Ensure dark mode compatibility

#### 3. **JavaScript Rendering** (Priority: MEDIUM)
**Current Issues:**
- `renderDefaultHeaderForm()` generates HTML with custom classes
- Grid rendering uses custom table classes
- Button rendering may use non-standard classes

**Required Changes:**
- Update `renderDefaultHeaderForm()` to use `.form-control`, `.form-label`, `.mb-3`
- Update grid rendering to use `.table`, `.table-bordered`, `.table-hover`
- Update button rendering to use `.btn`, `.btn-primary`, etc.
- Ensure responsive classes (`.col-md-6`, `.col-lg-4`)

#### 4. **Modal Component** (Priority: MEDIUM)
**Current Issues:**
- Inline styles in template
- Custom icon emojis (📋, 📊) - may not fit Dason aesthetic
- Hover effects using CSS variables

**Required Changes:**
- Use Dason modal structure with proper `.modal-header`, `.modal-body`
- Replace emojis with Feather icons or Font Awesome
- Use Bootstrap utilities for spacing (`.mb-3`, `.d-flex`)
- Use `.badge` for tags instead of custom `.ve-tag`

## Implementation Roadmap

### Phase 1: Template Standardization (Estimated: 2-3 hours)

#### Task 1.1: Add Breadcrumbs and Page Header
**File:** `accounting/templates/accounting/journal_entry.html`

```html
{% block content %}
<div class="page-content">
    <div class="container-fluid">
        <!-- Breadcrumbs -->
        <div class="row">
            <div class="col-12">
                <div class="page-title-box d-flex align-items-center justify-content-between">
                    <h4 class="mb-0">Journal Entry</h4>
                    <div class="page-title-right">
                        <ol class="breadcrumb m-0">
                            <li class="breadcrumb-item"><a href="{% url 'accounting:dashboard' %}">Accounting</a></li>
                            <li class="breadcrumb-item"><a href="{% url 'accounting:voucher_list' %}">Vouchers</a></li>
                            <li class="breadcrumb-item active">Journal Entry</li>
                        </ol>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <div id="app" ...>
                            <!-- Dynamic content rendered by JS -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock content %}
```

#### Task 1.2: Update Modal to Bootstrap 5 Standards
**File:** `accounting/templates/accounting/journal_entry.html`

```html
<div class="modal fade" id="voucherConfigModal" tabindex="-1" aria-labelledby="voucherConfigModalLabel" aria-hidden="true" data-bs-backdrop="static">
    <div class="modal-dialog modal-dialog-centered modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="voucherConfigModalLabel">
                    <i class="mdi mdi-clipboard-text-outline me-2"></i>
                    Select Voucher Configuration
                </h5>
            </div>
            <div class="modal-body">
                <p class="text-muted mb-3">Choose a configuration to begin your entry:</p>
                <div id="voucherConfigList" class="d-flex flex-column gap-2">
                    {% for config in voucher_configs %}
                    <div class="card mb-2 voucher-config-item" 
                         data-config-id="{{ config.config_id }}" 
                         data-journal-type="{{ config.journal_type_id }}"
                         style="cursor: pointer;">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <h6 class="mb-1">
                                        <i class="mdi mdi-file-document-outline me-2"></i>
                                        {{ config.name }}
                                    </h6>
                                    {% if config.description %}
                                    <p class="text-muted mb-0 small">{{ config.description }}</p>
                                    {% endif %}
                                </div>
                                <div class="text-end">
                                    <span class="badge bg-primary">{{ config.code }}</span>
                                    {% if config.journal_type %}
                                    <div class="text-muted small mt-1">{{ config.journal_type.name }}</div>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>
```

### Phase 2: CSS Consolidation (Estimated: 1-2 hours)

#### Task 2.1: Audit `voucher_entry_glass.css`
**Action Items:**
- Identify essential styles (animations, transitions, custom layouts)
- Identify conflicting styles (CSS variables, backdrop-filter)
- Identify dark mode specific styles

#### Task 2.2: Create `voucher_entry_dason.css`
**New File:** `accounting/static/accounting/css/voucher_entry_dason.css`

**Content Strategy:**
- Import Dason variables (if available)
- Add only custom enhancements that complement Dason
- Use Dason color palette
- Ensure dark mode compatibility

```css
/* Voucher Entry - Dason Compatible Styles */

/* Card hover effects */
.voucher-config-item {
    transition: all 0.2s ease;
}

.voucher-config-item:hover {
    box-shadow: 0 0.5rem 1rem rgba(0,0,0,.15);
    transform: translateY(-2px);
}

/* Dark mode support */
body[data-layout-mode=dark] .voucher-config-item:hover {
    box-shadow: 0 0.5rem 1rem rgba(0,0,0,.3);
}

/* Loading spinner */
.ve-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}

.ve-spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid #1c84ee;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Custom voucher entry enhancements */
/* Add only what's truly custom, not duplicating Dason */
```

#### Task 2.3: Update Template CSS Imports
**File:** `accounting/templates/accounting/journal_entry.html`

```html
{% block extra_css %}
{{ block.super }}
<link rel="stylesheet" href="{% static 'accounting/css/voucher_entry.css' %}">
<link rel="stylesheet" href="{% static 'accounting/css/voucher_entry_dason.css' %}">
<!-- Remove: voucher_entry_glass.css -->
{% endblock extra_css %}
```

### Phase 3: JavaScript Rendering Updates (Estimated: 2-3 hours)

#### Task 3.1: Update `renderDefaultHeaderForm()`
**File:** `accounting/static/accounting/js/voucher_entry.js`

**Current Approach:** Generates HTML with custom classes  
**New Approach:** Use Bootstrap 5 grid + Dason form classes

```javascript
renderDefaultHeaderForm() {
    const header = this.state.header;
    const html = `
        <div class="card mb-3">
            <div class="card-header">
                <h5 class="card-title mb-0">Header Information</h5>
            </div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-6 col-lg-4">
                        <label class="form-label">Date</label>
                        <input type="date" class="form-control" id="headerDate" value="${header.date || ''}">
                    </div>
                    <div class="col-md-6 col-lg-4">
                        <label class="form-label">Branch</label>
                        <select class="form-select" id="headerBranch">
                            <!-- Options populated by JS -->
                        </select>
                    </div>
                    <div class="col-md-6 col-lg-4">
                        <label class="form-label">Currency</label>
                        <select class="form-select" id="headerCurrency">
                            <!-- Options -->
                        </select>
                    </div>
                    <div class="col-md-6 col-lg-4">
                        <label class="form-label">Exchange Rate</label>
                        <input type="number" step="0.0001" class="form-control" id="headerExRate" value="${header.exRate || '1.0000'}">
                    </div>
                    <div class="col-md-6 col-lg-4">
                        <label class="form-label">Reference</label>
                        <input type="text" class="form-control" id="headerReference" value="${header.reference || ''}">
                    </div>
                    <div class="col-12">
                        <label class="form-label">Description</label>
                        <textarea class="form-control" id="headerDescription" rows="2">${header.description || ''}</textarea>
                    </div>
                </div>
                
                <!-- Dynamic fields from schema -->
                ${this.renderDynamicHeaderFields()}
            </div>
        </div>
    `;
    return html;
}
```

#### Task 3.2: Update Grid/Table Rendering
**File:** `accounting/static/accounting/js/voucher_entry.js`

```javascript
renderGrid() {
    return `
        <div class="card">
            <div class="card-header">
                <div class="d-flex justify-content-between align-items-center">
                    <h5 class="card-title mb-0">Journal Lines</h5>
                    <button class="btn btn-primary btn-sm" onclick="voucherApp.addRow()">
                        <i class="mdi mdi-plus me-1"></i>Add Line
                    </button>
                </div>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-bordered table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                ${this.renderColumnHeaders()}
                            </tr>
                        </thead>
                        <tbody id="voucherLines">
                            ${this.renderRows()}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card-footer">
                ${this.renderTotals()}
            </div>
        </div>
    `;
}
```

#### Task 3.3: Update Button Rendering
**File:** `accounting/static/accounting/js/voucher_entry.js`

```javascript
renderActionButtons() {
    const { can_submit, can_approve, can_post } = this.permissions;
    
    return `
        <div class="card">
            <div class="card-body">
                <div class="d-flex gap-2 justify-content-end">
                    <button class="btn btn-secondary" onclick="voucherApp.cancel()">
                        <i class="mdi mdi-close me-1"></i>Cancel
                    </button>
                    <button class="btn btn-info" onclick="voucherApp.saveDraft()">
                        <i class="mdi mdi-content-save-outline me-1"></i>Save Draft
                    </button>
                    ${can_submit ? `
                        <button class="btn btn-primary" onclick="voucherApp.submit()">
                            <i class="mdi mdi-send me-1"></i>Submit
                        </button>
                    ` : ''}
                    ${can_approve ? `
                        <button class="btn btn-success" onclick="voucherApp.approve()">
                            <i class="mdi mdi-check-circle-outline me-1"></i>Approve
                        </button>
                    ` : ''}
                    ${can_post ? `
                        <button class="btn btn-success" onclick="voucherApp.post()">
                            <i class="mdi mdi-publish me-1"></i>Post
                        </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}
```

### Phase 4: Icon Updates (Estimated: 30 minutes)

#### Task 4.1: Replace Emoji with Feather/Material Design Icons
**Dason Icon Libraries:**
- Material Design Icons (MDI): `mdi mdi-icon-name`
- Feather Icons: `<i data-feather="icon-name"></i>`

**Common Icons for Voucher Entry:**
- Document: `mdi-file-document-outline`
- Add: `mdi-plus`
- Edit: `mdi-pencil-outline`
- Delete: `mdi-delete-outline`
- Save: `mdi-content-save-outline`
- Send/Submit: `mdi-send`
- Approve: `mdi-check-circle-outline`
- Reject: `mdi-close-circle-outline`
- Post: `mdi-publish`
- Calendar: `mdi-calendar`
- Money: `mdi-currency-usd`
- Account: `mdi-book-outline`

## Testing Checklist

### Visual Testing
- [ ] Page loads with proper breadcrumbs
- [ ] Page title and actions display correctly
- [ ] Cards have proper shadows and borders
- [ ] Forms use consistent spacing (mb-3 between fields)
- [ ] Tables are responsive and bordered
- [ ] Buttons use Dason colors (primary, success, danger)
- [ ] Modal displays with proper Bootstrap 5 structure
- [ ] Icons render correctly (MDI)
- [ ] Dark mode works properly

### Functional Testing
- [ ] Schema loads from configuration (no regression)
- [ ] Header fields render dynamically
- [ ] Line fields render dynamically
- [ ] Add/delete lines works
- [ ] Totals calculate correctly
- [ ] Save/Submit/Approve actions work
- [ ] Config selection modal works
- [ ] Responsive design works on mobile/tablet

### Browser Testing
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile browsers (iOS Safari, Chrome Android)

## Migration Strategy

### Step 1: Create Backup
```bash
cp accounting/templates/accounting/journal_entry.html accounting/templates/accounting/journal_entry.html.backup
cp accounting/static/accounting/css/voucher_entry_glass.css accounting/static/accounting/css/voucher_entry_glass.css.backup
```

### Step 2: Implement Changes Incrementally
1. Update template structure (breadcrumbs, page header, card)
2. Test page loads correctly
3. Update modal structure
4. Test modal works
5. Create `voucher_entry_dason.css`
6. Update CSS imports
7. Test visual appearance
8. Update JavaScript rendering functions
9. Test functionality
10. Replace icons
11. Final testing

### Step 3: Validation
- Run Django development server
- Visit `/accounting/journal-entry/`
- Verify config modal appears if no config in URL
- Select config and verify form renders
- Test all CRUD operations
- Test responsive design
- Test dark mode toggle

## File Checklist

### Files to Modify
- [ ] `accounting/templates/accounting/journal_entry.html` - Template structure
- [ ] `accounting/static/accounting/js/voucher_entry.js` - Rendering functions
- [ ] `accounting/static/accounting/css/voucher_entry.css` - Review and clean up

### Files to Create
- [ ] `accounting/static/accounting/css/voucher_entry_dason.css` - Dason-compatible enhancements

### Files to Deprecate (optional)
- [ ] `accounting/static/accounting/css/voucher_entry_glass.css` - May keep as backup

## Success Criteria

✅ **Visual Consistency:** Voucher entry page matches the look and feel of other Dason pages (user detail, voucher config detail)  
✅ **No Regressions:** All schema-driven functionality continues to work  
✅ **Dark Mode:** Page adapts correctly to dark mode  
✅ **Responsive:** Works on desktop, tablet, and mobile  
✅ **Accessibility:** Proper ARIA labels, keyboard navigation  
✅ **Performance:** No degradation in load time or rendering speed  

## Post-Implementation

### Documentation
- Update `00_START_HERE.md` with UI standardization completion
- Add screenshots to documentation
- Document any Dason-specific customizations

### Future Enhancements
- Consider adding loading states with Dason spinners
- Add toast notifications using Dason toastr integration
- Implement keyboard shortcuts (Ctrl+S for save, etc.)
- Add field validation with Dason form validation styles

---

**Prepared by:** GitHub Copilot  
**Date:** 2025  
**Status:** Ready for Implementation
