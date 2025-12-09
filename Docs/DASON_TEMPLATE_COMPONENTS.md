# Dason Admin Template - Component Documentation

This document provides a comprehensive reference for the Dason admin template components, inheritance hierarchy, and usage patterns in the Himalytix ERP system.

---

## Table of Contents

1. [Overview](#overview)
2. [Template Inheritance Hierarchy](#template-inheritance-hierarchy)
3. [Core Partials](#core-partials)
4. [Base Templates](#base-templates)
5. [Reusable Components](#reusable-components)
6. [Module-Specific List/Form Bases](#module-specific-listform-bases)
7. [Widgets](#widgets)
8. [Static Assets](#static-assets)
9. [Template Tags and Filters](#template-tags-and-filters)
10. [Common Patterns](#common-patterns)
11. [Theme Customization](#theme-customization)
12. [Quick Reference](#quick-reference)

---

## Overview

The project uses the **Dason Admin Template**, a Bootstrap 5-based dashboard template. The template system follows Django's template inheritance model with multiple layers:

```
partials/base.html (Root)
    └── base.html (App wrapper)
        └── components/base/*.html (Generic components)
            └── {app}/_list_base.html / _form_base.html (Module base)
                └── {entity}_list.html / {entity}_form.html (Page templates)
```

### Key Technologies
- **Bootstrap 5**: CSS framework
- **HTMX**: Dynamic content loading without full page reloads
- **MetisMenu**: Sidebar navigation menu
- **SimpleBar**: Custom scrollbar styling
- **DataTables**: Interactive data tables with sorting/filtering/export
- **Feather Icons & MDI**: Icon libraries
- **Toastr**: Toast notifications
- **Flatpickr**: Date picker
- **Nepali Datepicker**: Dual calendar support (AD/BS)

---

## Template Inheritance Hierarchy

### Visual Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    partials/base.html                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ <html>                                                   │  │
│  │   <head>                                                 │  │
│  │     {% block title %}                                    │  │
│  │     {% block css %}                                      │  │
│  │     {% block extra_css %}                                │  │
│  │   </head>                                                │  │
│  │   <body data-layout-mode="light" data-sidebar="dark">    │  │
│  │     {% include "partials/left-sidebar.html" %}           │  │
│  │     <div class="main-content">                           │  │
│  │       {% include "partials/header.html" %}               │  │
│  │       {% block content %}                                │  │
│  │       {% include "partials/footer.html" %}               │  │
│  │     </div>                                               │  │
│  │     {% include "partials/right-sidebar.html" %}          │  │
│  │     {% block javascript %}                               │  │
│  │     {% block extra_js %}                                 │  │
│  │   </body>                                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Inheritance Chain Examples

#### List Page
```
partials/base.html
    └── accounting/_list_base.html
        └── accounting/sales_order_list.html
```

#### Form Page
```
partials/base.html
    └── components/base/form_base.html
        └── accounting/sales_order_form.html
```

---

## Core Partials

Located in `templates/partials/`:

### `base.html` (384 lines)
**Purpose**: Root HTML document structure

**Available Blocks**:
| Block Name | Purpose | Default Content |
|------------|---------|-----------------|
| `title` | Page title in `<title>` tag | "Dason" |
| `css` | Core CSS includes | Bootstrap, App CSS |
| `extra_css` | Additional page CSS | Empty |
| `content` | Main page content | Empty |
| `javascript` | Core JS includes | jQuery, Bootstrap, HTMX, etc. |
| `extra_js` | Additional page JS | Empty |
| `footer` | Footer area | Includes partials/footer.html |

**Body Data Attributes**:
```html
<body data-layout-mode="light"
      data-sidebar="dark"
      data-topbar="light"
      data-sidebar-image="none"
      data-layout="vertical">
```

**Key Includes**:
```django
{% include "partials/left-sidebar.html" %}
{% include "partials/header.html" %}
{% include "partials/footer.html" %}
{% include "partials/right-sidebar.html" %}
```

### `header.html` (~150 lines)
**Purpose**: Top navigation bar

**Contains**:
- Logo (links to dashboard)
- Mobile menu toggle
- Search bar (Ctrl+K shortcut)
- Language/Region switcher
- Organization switcher (multi-tenant)
- User profile dropdown
  - Profile settings
  - Lock screen
  - Logout

**Key Features**:
```html
<!-- Search with keyboard shortcut -->
<span class="input-group-text"><kbd>⌘</kbd>+<kbd>K</kbd></span>

<!-- Organization Switcher -->
<div class="dropdown d-inline-block" id="org-switcher">
    <!-- HTMX-powered organization selection -->
</div>
```

### `left-sidebar.html` (845 lines)
**Purpose**: Main navigation sidebar

**Structure**:
```html
<div class="vertical-menu">
    <div data-simplebar class="h-100">
        <div id="sidebar-menu">
            <ul class="metismenu list-unstyled" id="side-menu">
                <!-- Menu items with permission checks -->
            </ul>
        </div>
    </div>
</div>
```

**Permission-Gated Navigation Pattern**:
```django
{% load permission_tags %}

{% if user|has_permission:'accounting_invoice_view' %}
<li>
    <a href="{% url 'accounting:invoice_list' %}">
        <i data-feather="file-text"></i>
        <span>{% trans "Invoices" %}</span>
    </a>
</li>
{% endif %}
```

**Menu Structure**:
- Dashboard
- Accounting (submenu)
  - Chart of Accounts
  - Fiscal Years
  - Customers/Suppliers
  - Invoices
  - Sales Orders
  - Delivery Notes
  - Journal Entries
  - Vouchers
  - Reports
- Inventory (submenu)
- Purchasing (submenu)
- Service Management (submenu)
- Enterprise Features (submenu)
- User Management (submenu)
- Settings

### `right-sidebar.html` (185 lines)
**Purpose**: Theme customizer panel

**Settings Available**:
- Layout (Vertical/Horizontal)
- Layout Mode (Light/Dark)
- Text Size (XS/S/M/L/XL)
- Font Family (Inter, Roboto, Source Sans, Poppins)
- Layout Width (Fluid/Boxed)
- Sidebar Color
- Topbar Color

**Usage Pattern**:
```html
<input type="radio" name="layout-mode" value="dark" data-setting="layout-mode">
```
Settings persist to localStorage via `js/app.js`.

### `footer.html` (~20 lines)
**Purpose**: Page footer

**Content**:
```html
<footer class="footer">
    <div class="container-fluid">
        <div class="row">
            <div class="col-sm-6">© {year} Himalytix.</div>
            <div class="col-sm-6">Design & Develop by Themesdesign</div>
        </div>
    </div>
</footer>
```

---

## Base Templates

### `templates/base.html`
**Purpose**: App wrapper that extends partials/base.html

```django
{% extends 'partials/base.html' %}
{% load static %}

{% block content %}
<div class="main-content">
    <div class="page-content">
        <div class="container-fluid">
            {% block page_content %}{% endblock %}
        </div>
    </div>
</div>
{% endblock %}
```

---

## Reusable Components

Located in `templates/components/base/`:

### `form_base.html` (190 lines)
**Purpose**: Base template for form pages

**Extends**: `partials/base.html`

**Available Blocks**:
| Block | Purpose |
|-------|---------|
| `page_title` | Page title |
| `form_heading` | Form header text |
| `form_title_text` | Card title |
| `form_content` | Form body content |

**Key Features**:
- Breadcrumb navigation
- Unsaved changes indicator
- Expandable form shell
- Sticky action buttons
- Validation styling

**Context Variables**:
| Variable | Type | Description |
|----------|------|-------------|
| `page_title` | string | Page heading |
| `form_title` | string | Form card title |
| `form_subtitle` | string | Optional subtitle |
| `breadcrumbs` | list | [(name, url), ...] |
| `form_shell_id` | string | DOM ID for form shell |

**Usage Example**:
```django
{% extends 'components/base/form_base.html' %}

{% block form_content %}
<form method="post">
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit">Save</button>
</form>
{% endblock %}
```

### `list_base.html` (261 lines)
**Purpose**: Base template for list/table pages

**Extends**: `partials/base.html`

**Available Blocks**:
| Block | Purpose |
|-------|---------|
| `list_page_title` | Page heading |
| `list_metrics` | Quick metrics cards |
| `list_toolbar` | Search/filter toolbar |
| `table_content` | Table structure |

**Key Features**:
- Loading overlay
- Toast container
- Expandable list shell
- Search toolbar with keyboard shortcut
- DataTables integration

### `form.html` (107 lines)
**Purpose**: Reusable form component (include, not extend)

**Usage**:
```django
{% include 'components/base/form.html' with form_title="Create Customer" form=form %}
```

**Context Variables**:
| Variable | Default | Description |
|----------|---------|-------------|
| `form_title` | "Form" | Card header |
| `form_description` | - | Optional description |
| `form_id` | "dynamic-form" | Form DOM ID |
| `multipart` | false | Enable file uploads |
| `submit_label` | "Submit" | Submit button text |
| `cancel_url` | - | Cancel link URL |

### `dialog.html`
**Purpose**: Bootstrap modal dialog component

**Usage**:
```django
{% include 'components/base/dialog.html' with title="Confirm Delete" size="md" show_footer=True %}
```

**Variables**:
| Variable | Options | Description |
|----------|---------|-------------|
| `title` | string | Modal title |
| `size` | sm/md/lg/xl | Modal size |
| `show_footer` | bool | Show footer buttons |

**Blocks**:
- `dialog_body`: Modal content
- `dialog_footer`: Action buttons

### `pagination.html`
**Purpose**: Page navigation component

**Usage**:
```django
{% include 'components/base/pagination.html' %}
```

**Required Context**:
- `page_obj`: Django Paginator page object
- `page_range`: Iterable of page numbers

### `table_htmx.html` (257 lines)
**Purpose**: HTMX-powered interactive table

**Features**:
- HTMX refresh without page reload
- Sortable columns
- Bulk actions with checkboxes
- Export (Excel, CSV, PDF)
- Filter panel
- Loading indicators

**Context Variables**:
| Variable | Description |
|----------|-------------|
| `table_id` | DOM ID for table |
| `columns` | Column definitions |
| `bulk_actions` | Bulk action buttons |
| `export_formats` | Export format options |
| `filter_config` | Filter panel config |

**Column Definition**:
```python
columns = [
    {'name': 'code', 'label': 'Code', 'sortable': True, 'width': '100px'},
    {'name': 'name', 'label': 'Name', 'sortable': True, 'align': 'left'},
]
```

### `table_filters.html`
**Purpose**: Filter panel for HTMX tables

**Filter Types**:
- `select`: Dropdown selection
- `date`: Single date picker
- `daterange`: Date range (from/to)
- `text`: Text input

**Config Example**:
```python
filter_config = {
    'filters': {
        'status': {
            'type': 'select',
            'label': 'Status',
            'choices': [{'value': 'active', 'label': 'Active'}]
        },
        'created_at': {
            'type': 'daterange',
            'label': 'Created Date'
        }
    }
}
```

---

## Module-Specific List/Form Bases

Each module has its own `_list_base.html` and `_form_base.html` in its templates folder.

### Accounting Module
**Location**: `accounting/templates/accounting/`

#### `_list_base.html` (405 lines)
Extended by: `sales_order_list.html`, `invoice_list.html`, etc.

**Special Features**:
- Smart filters integration
- Compact layout for data-dense views
- DataTables with export buttons

**Blocks**:
| Block | Purpose |
|-------|---------|
| `create_button` | Add new button area |
| `table_head` | Table headers |
| `table_body` | Table rows |
| `extra_filters` | Additional filter controls |

### Inventory Module
**Location**: `inventory/templates/Inventory/`

#### `_list_base.html`
Extended by: `product_list.html`, `warehouse_list.html`, etc.

**Blocks**:
| Block | Purpose |
|-------|---------|
| `table_head` | Table headers |
| `table_body` | Table rows |

#### `_form_base.html`
Extended by: `product_form.html`, `warehouse_form.html`, etc.

**Blocks**:
| Block | Purpose |
|-------|---------|
| `form_content` | Form body |

### Service Management Module
**Location**: `service_management/templates/service_management/`

#### `_list_base.html`
Extended by: `serviceticket_list.html`, `servicecontract_list.html`, etc.

---

## Widgets

Located in `templates/widgets/`:

### `dual_calendar_widget.html`
**Purpose**: Nepali (BS) / Gregorian (AD) date picker

**Usage**: Automatically used by `DualCalendarWidget` form widget

**Modes**:
- `AD`: Gregorian only
- `BS`: Nepali only
- `DUAL`: Toggle between both

**HTML Structure**:
```html
<div class="input-group dual-calendar-picker"
     data-dual-calendar
     data-calendar-mode="{{ widget.mode }}"
     data-initial-view="{{ widget.start_view }}">
    <input name="{{ widget.bs_name }}" data-role="bs-input">
    <input name="{{ widget.ad_name }}" data-role="ad-input">
    <button data-role="toggle">AD/BS</button>
</div>
```

---

## Static Assets

### CSS Files
Located in `static/css/`:

| File | Purpose |
|------|---------|
| `bootstrap.min.css` | Bootstrap 5 framework |
| `app.min.css` | Dason theme styles |
| `icons.min.css` | Icon fonts |
| `custom.min.css` | Project customizations |

### JavaScript Files
Located in `static/js/`:

| File | Purpose |
|------|---------|
| `app.js` | Theme initialization, sidebar, settings |
| `pages/*.js` | Page-specific functionality |

### Third-Party Libraries
Located in `static/libs/`:

| Library | Purpose |
|---------|---------|
| `jquery` | DOM manipulation |
| `bootstrap` | UI components |
| `metismenu` | Sidebar navigation |
| `simplebar` | Custom scrollbars |
| `feather-icons` | Icon system |
| `datatables.net` | Data tables |
| `flatpickr` | Date picker |
| `toastr` | Toast notifications |
| `htmx.org` | Dynamic HTML |
| `nepali-datepicker` | BS calendar |

---

## Template Tags and Filters

### Permission Tags
**Load**: `{% load permission_tags %}`

| Filter | Usage | Description |
|--------|-------|-------------|
| `has_permission` | `user\|has_permission:'codename'` | Check single permission |
| `has_any_permission` | `user\|has_any_permission:'code1,code2'` | Check any of multiple |
| `has_all_permissions` | `user\|has_all_permissions:'code1,code2'` | Check all permissions |

**Permission Codename Format**: `{module}_{entity}_{action}`

**Example**:
```django
{% if user|has_permission:'accounting_invoice_view' %}
    <a href="{% url 'accounting:invoice_list' %}">Invoices</a>
{% endif %}
```

### Standard Django Tags
```django
{% load static %}       {# Static file URLs #}
{% load i18n %}         {# Translation support #}
```

---

## Common Patterns

### Creating a List Page

```django
{% extends 'accounting/_list_base.html' %}
{% load i18n %}

{% block title %}{% trans "My Items" %}{% endblock %}

{% block table_head %}
<thead>
    <tr>
        <th>{% trans "Code" %}</th>
        <th>{% trans "Name" %}</th>
        <th>{% trans "Status" %}</th>
        <th>{% trans "Actions" %}</th>
    </tr>
</thead>
{% endblock %}

{% block table_body %}
<tbody>
    {% for item in items %}
    <tr>
        <td>{{ item.code }}</td>
        <td>{{ item.name }}</td>
        <td>
            <span class="badge bg-{{ item.status|yesno:'success,secondary' }}">
                {{ item.get_status_display }}
            </span>
        </td>
        <td>
            <a href="{% url 'app:item_edit' item.pk %}" 
               class="btn btn-sm btn-outline-primary">
                <i class="mdi mdi-pencil"></i>
            </a>
        </td>
    </tr>
    {% empty %}
    <tr>
        <td colspan="4" class="text-center text-muted">No items found.</td>
    </tr>
    {% endfor %}
</tbody>
{% endblock %}
```

### Creating a Form Page

```django
{% extends 'components/base/form_base.html' %}
{% load static i18n %}

{% block page_title %}{% trans "Create Item" %}{% endblock %}

{% block form_content %}
<form method="post" id="item-form">
    {% csrf_token %}
    
    <div class="row">
        <div class="col-md-6 mb-3">
            <label class="form-label">{{ form.name.label }}</label>
            {{ form.name }}
            {% if form.name.errors %}
            <div class="invalid-feedback d-block">{{ form.name.errors }}</div>
            {% endif %}
        </div>
        <!-- More fields... -->
    </div>
    
    <div class="mt-4">
        <button type="submit" class="btn btn-primary">
            <i class="mdi mdi-content-save me-1"></i> {% trans "Save" %}
        </button>
        <a href="{% url 'app:item_list' %}" class="btn btn-secondary">
            {% trans "Cancel" %}
        </a>
    </div>
</form>
{% endblock %}

{% block extra_js %}
{{ block.super }}
<script>
    // Page-specific JavaScript
</script>
{% endblock %}
```

### HTMX Dynamic Content

```django
{# Button that loads content dynamically #}
<button hx-get="{% url 'app:item_detail' item.pk %}"
        hx-target="#modal-content"
        hx-swap="innerHTML"
        class="btn btn-info">
    View Details
</button>

{# Content area #}
<div id="modal-content"></div>
```

### Adding Menu Item with Permission

In `partials/left-sidebar.html`:
```django
{% if user|has_permission:'mymodule_myentity_view' %}
<li>
    <a href="{% url 'mymodule:myentity_list' %}" class="waves-effect">
        <i data-feather="box"></i>
        <span>{% trans "My Entity" %}</span>
    </a>
</li>
{% endif %}
```

---

## Theme Customization

### Dark Mode
Toggle via right sidebar or programmatically:
```javascript
document.body.setAttribute('data-layout-mode', 'dark');
```

### Sidebar Variants
```html
<body data-sidebar="dark">   <!-- Dark sidebar -->
<body data-sidebar="light">  <!-- Light sidebar -->
<body data-sidebar="brand">  <!-- Branded sidebar -->
```

### Layout Modes
```html
<body data-layout="vertical">    <!-- Standard layout -->
<body data-layout="horizontal">  <!-- Top nav layout -->
```

### Text Scaling
CSS variables for text size:
```css
:root {
    --text-scale-xs: 0.8;
    --text-scale-s: 0.9;
    --text-scale-m: 1;
    --text-scale-l: 1.1;
    --text-scale-xl: 1.2;
}
```

---

## Quick Reference

### File Locations

| Type | Location |
|------|----------|
| Core partials | `templates/partials/` |
| Base components | `templates/components/base/` |
| Module templates | `{app}/templates/{app}/` |
| Widgets | `templates/widgets/` |
| Static CSS | `static/css/` |
| Static JS | `static/js/` |
| Third-party libs | `static/libs/` |

### Block Inheritance Chain

```
partials/base.html
├── {% block title %}
├── {% block css %}
├── {% block extra_css %}
├── {% block content %}
│   └── (Override in child templates)
├── {% block javascript %}
└── {% block extra_js %}
```

### Common Template Tags

```django
{% load static %}                     {# Load static files #}
{% load i18n %}                       {# Load translations #}
{% load permission_tags %}            {# Load permission filters #}

{% static 'path/to/file' %}           {# Static file URL #}
{% url 'app:view_name' arg %}         {# Reverse URL #}
{% trans "Text" %}                    {# Translate text #}
{% csrf_token %}                      {# CSRF protection #}

{{ user|has_permission:'codename' }}  {# Check permission #}
```

### CSS Classes Quick Reference

| Class | Description |
|-------|-------------|
| `main-content` | Main content wrapper |
| `page-content` | Page body wrapper |
| `container-fluid` | Full-width container |
| `card` | Card component |
| `card-header` | Card header |
| `card-body` | Card content |
| `table-responsive` | Scrollable table wrapper |
| `btn btn-{color}` | Button (primary, secondary, success, danger, etc.) |
| `badge bg-{color}` | Badge/pill |
| `form-control` | Form input |
| `form-select` | Select dropdown |
| `form-label` | Input label |
| `invalid-feedback` | Validation error message |

---

## Related Documentation

- [Permissions and Authorization](./PERMISSIONS_AND_AUTHORIZATION.md)
- [Dual Calendar Datepicker Reference](./DUAL_CALENDAR_DATEPICKER_REFERENCE.md)
- [UI/UX Consistency Plan](./UI_UX_CONSISTENCY_PLAN.md)

---

*Last updated: Session documentation*
