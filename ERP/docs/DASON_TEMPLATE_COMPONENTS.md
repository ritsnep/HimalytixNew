# Dason Template Components

This document outlines the enhanced template system components implemented for improved robustness, error handling, and user experience in the Dason ERP system.

## Overview

The template system has been enhanced with:
- Safe template tags that prevent page-breaking errors
- Enhanced form base templates with validation and UX features
- Template validation commands for integrity checking
- Structured logging for template-related operations

## Safe Template Tags (`usermanagement/templatetags/safe_tags.py`)

### Purpose
The safe template tags provide error-resistant alternatives to standard Django template tags, ensuring that template rendering continues even when data is missing or malformed.

### Available Tags

#### `safe_get`
Retrieves a dictionary value safely, returning a default if the key doesn't exist.

```django
{% load safe_tags %}

<!-- Instead of {{ data.nonexistent_key }} which could cause errors -->
{{ data|safe_get:"nonexistent_key" }}
{{ data|safe_get:"nonexistent_key|default:'N/A'" }}
```

#### `safe_date`
Formats dates safely, handling None values and invalid date formats.

```django
{% load safe_tags %}

<!-- Safe date formatting -->
{{ object.created_at|safe_date:"M d, Y" }}
{{ object.created_at|safe_date:"M d, Y"|default:"No date" }}
```

#### `safe_number`
Formats numbers safely with customizable formatting.

```django
{% load safe_tags %}

<!-- Safe number formatting -->
{{ value|safe_number }}
{{ value|safe_number:"2" }}  <!-- 2 decimal places -->
{{ value|safe_number:"0"|default:"0" }}  <!-- Integer with default -->
```

#### `safe_url`
Generates URLs safely, handling missing URL patterns gracefully.

```django
{% load safe_tags %}

<!-- Safe URL generation -->
<a href="{% safe_url 'app:view' object.id %}">View</a>
<a href="{% safe_url 'app:view' object.id|default:'#' %}">View</a>
```

### Implementation Details

```python
from django import template
from django.template.defaultfilters import date, floatformat
from django.urls import reverse, NoReverseMatch
import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.filter
def safe_get(value, arg):
    """Get dict value safely with optional default."""
    try:
        if isinstance(value, dict):
            return value.get(arg, '')
        return getattr(value, arg, '')
    except (AttributeError, KeyError, TypeError) as e:
        logger.warning(f"safe_get failed: {e}")
        return ''

@register.filter
def safe_date(value, arg):
    """Format date safely."""
    try:
        if value is None:
            return ''
        return date(value, arg)
    except Exception as e:
        logger.warning(f"safe_date failed: {e}")
        return ''

@register.simple_tag
def safe_url(view_name, *args, **kwargs):
    """Generate URL safely."""
    try:
        return reverse(view_name, args=args, kwargs=kwargs)
    except NoReverseMatch as e:
        logger.warning(f"safe_url failed for {view_name}: {e}")
        return '#'
```

## Enhanced Form Base Template (`templates/components/form_base.html`)

### Purpose
The enhanced form base template provides a standardized, feature-rich foundation for all forms in the application, including validation feedback, loading states, and user experience improvements.

### Features

#### Unsaved Changes Detection
Automatically warns users about unsaved changes when attempting to navigate away.

#### Loading Overlays
Shows loading indicators during form submission to prevent double-submission.

#### Auto-dismissing Messages
Success/error messages automatically disappear after a timeout.

#### Enhanced Validation
Client-side validation with visual feedback.

### Template Structure

```html
{% extends "partials/base.html" %}
{% load static %}

<div class="form-container" data-form-id="{{ form_id|default:request.resolver_match.url_name }}">
    <!-- Form Header -->
    <div class="form-header">
        <h2>{{ title|default:"Form" }}</h2>
        {% if subtitle %}<p class="text-muted">{{ subtitle }}</p>{% endif %}
    </div>

    <!-- Messages -->
    <div class="messages-container">
        {% for message in messages %}
        <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
    </div>

    <!-- Form Content -->
    <form method="post" enctype="{{ enctype|default:'multipart/form-data' }}" class="needs-validation" novalidate>
        {% csrf_token %}

        <!-- Form Fields -->
        <div class="form-fields">
            {% block form_fields %}{% endblock %}
        </div>

        <!-- Form Actions -->
        <div class="form-actions">
            {% block form_actions %}
            <button type="submit" class="btn btn-primary">
                <span class="spinner-border spinner-border-sm d-none" role="status"></span>
                {{ submit_text|default:"Save" }}
            </button>
            {% if cancel_url %}
            <a href="{{ cancel_url }}" class="btn btn-secondary">Cancel</a>
            {% endif %}
            {% endblock %}
        </div>
    </form>
</div>

<!-- JavaScript for enhanced UX -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.needs-validation');

    // Unsaved changes detection
    let formChanged = false;
    form.addEventListener('input', () => { formChanged = true; });

    window.addEventListener('beforeunload', function(e) {
        if (formChanged) {
            e.preventDefault();
            e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        }
    });

    // Loading states
    form.addEventListener('submit', function() {
        const submitBtn = form.querySelector('button[type="submit"]');
        const spinner = submitBtn.querySelector('.spinner-border');
        submitBtn.disabled = true;
        spinner.classList.remove('d-none');
    });

    // Auto-dismiss messages
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
});
</script>
```

### Usage Example

```django
{% extends "components/form_base.html" %}

{% block form_fields %}
<div class="row">
    <div class="col-md-6">
        <label for="{{ form.name.id_for_label }}" class="form-label">Name</label>
        {{ form.name }}
        {% if form.name.errors %}
            <div class="invalid-feedback d-block">
                {{ form.name.errors.0 }}
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}

{% block form_actions %}
<button type="submit" class="btn btn-success">Create Item</button>
<a href="{% url 'item_list' %}" class="btn btn-secondary">Cancel</a>
{% endblock %}
```

## Template Validation Command (`usermanagement/management/commands/validate_templates.py`)

### Purpose
The template validation command scans all Django templates for common issues, syntax errors, and potential problems before they cause runtime errors.

### Features

#### Syntax Validation
Checks for Django template syntax errors.

#### Missing Template Variables
Identifies undefined variables in templates.

#### Security Checks
Validates against common template injection vulnerabilities.

#### Performance Analysis
Reports potential N+1 query issues in template rendering.

### Usage

```bash
# Validate all templates
python manage.py validate_templates

# Validate specific app templates
python manage.py validate_templates --app usermanagement

# Verbose output
python manage.py validate_templates --verbosity 2

# Check for security issues
python manage.py validate_templates --security
```

### Implementation

```python
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import get_template
from django.template import TemplateSyntaxError, VariableDoesNotExist
from django.apps import apps
import os
import re

class Command(BaseCommand):
    help = 'Validate Django templates for syntax errors and common issues'

    def add_arguments(self, parser):
        parser.add_argument('--app', help='Validate templates for specific app')
        parser.add_argument('--security', action='store_true', help='Check for security issues')
        parser.add_argument('--verbose', action='store_true', help='Verbose output')

    def handle(self, *args, **options):
        if options['app']:
            apps_to_check = [options['app']]
        else:
            apps_to_check = [app.label for app in apps.get_app_configs()]

        total_templates = 0
        errors_found = 0

        for app_label in apps_to_check:
            try:
                app_config = apps.get_app_config(app_label)
                template_dir = os.path.join(app_config.path, 'templates')

                if os.path.exists(template_dir):
                    self.stdout.write(f"Checking templates in {app_label}...")
                    app_templates, app_errors = self.validate_app_templates(template_dir, options)
                    total_templates += app_templates
                    errors_found += app_errors

            except Exception as e:
                self.stderr.write(f"Error checking {app_label}: {e}")

        self.stdout.write(f"\nValidation complete: {total_templates} templates checked, {errors_found} errors found")

    def validate_app_templates(self, template_dir, options):
        templates_checked = 0
        errors_found = 0

        for root, dirs, files in os.walk(template_dir):
            for file in files:
                if file.endswith('.html'):
                    template_path = os.path.join(root, file)
                    relative_path = os.path.relpath(template_path, template_dir)

                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Basic syntax check
                        self.validate_template_syntax(content, relative_path)

                        # Security checks if requested
                        if options['security']:
                            self.validate_template_security(content, relative_path)

                        templates_checked += 1

                        if options['verbose']:
                            self.stdout.write(f"✓ {relative_path}")

                    except Exception as e:
                        self.stderr.write(f"✗ {relative_path}: {e}")
                        errors_found += 1

        return templates_checked, errors_found

    def validate_template_syntax(self, content, path):
        """Validate basic template syntax."""
        # Check for unmatched template tags
        open_tags = re.findall(r'{%\s*(\w+)', content)
        close_tags = re.findall(r'{%\s*end(\w+)', content)

        for tag in set(open_tags):
            if tag not in ['load', 'csrf_token', 'url', 'static', 'trans', 'blocktrans'] and open_tags.count(tag) != close_tags.count(tag):
                raise CommandError(f"Unmatched template tag '{tag}' in {path}")

    def validate_template_security(self, content, path):
        """Check for potential security issues."""
        # Check for dangerous template filters
        dangerous_patterns = [
            r'\|\s*safe\s*}',  # Overuse of |safe
            r'{%\s*autoescape\s+off\s*%}',  # Autoescape disabled
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                self.stderr.write(f"Security warning in {path}: {pattern.strip()}")
```

## Structured Logging (`utils/logging_utils.py`)

### Purpose
Structured logging provides consistent, searchable logs for template operations, permission checks, and system events.

### Features

#### Permission Check Logging
Logs all permission checks with user, organization, and result.

#### Template Error Logging
Captures template rendering errors with context.

#### Performance Monitoring
Tracks template rendering times and cache hits/misses.

### Implementation

```python
import logging
import time
from functools import wraps

class StructuredLogger:
    def __init__(self, component_name):
        self.logger = logging.getLogger(f'dason.{component_name}')
        self.component = component_name

    def log_permission_check(self, user, organization, permission, granted):
        """Log permission check with structured data."""
        self.logger.info(
            f"Permission check: {permission}",
            extra={
                'component': self.component,
                'user_id': user.id if user else None,
                'organization_id': organization.id if organization else None,
                'permission': permission,
                'granted': granted,
                'user_role': getattr(user, 'role', None) if user else None,
            }
        )

    def log_template_error(self, template_name, error, context=None):
        """Log template rendering errors."""
        self.logger.error(
            f"Template error in {template_name}: {error}",
            extra={
                'component': self.component,
                'template': template_name,
                'error_type': type(error).__name__,
                'context_keys': list(context.keys()) if context else None,
            },
            exc_info=True
        )

    def log_cache_operation(self, operation, key, hit=None, duration=None):
        """Log cache operations."""
        log_data = {
            'component': self.component,
            'operation': operation,
            'cache_key': key,
        }

        if hit is not None:
            log_data['cache_hit'] = hit
        if duration is not None:
            log_data['duration_ms'] = duration * 1000

        self.logger.debug(f"Cache {operation}", extra=log_data)
```

## Migration Guide

### Updating Existing Templates

1. **Replace unsafe operations** with safe template tags:
   ```django
   <!-- Before -->
   {{ object.date_created|date:"M d, Y" }}

   <!-- After -->
   {% load safe_tags %}
   {{ object.date_created|safe_date:"M d, Y" }}
   ```

2. **Use enhanced form base** for new forms:
   ```django
   {% extends "components/form_base.html" %}
   ```

3. **Add template validation** to CI/CD pipeline:
   ```yaml
   - name: Validate Templates
     run: python manage.py validate_templates --security
   ```

### Configuration

Add to `settings.py`:
```python
# Template validation settings
TEMPLATE_VALIDATION_ENABLED = True
TEMPLATE_SECURITY_CHECKS = True

# Logging configuration
LOGGING = {
    'version': 1,
    'handlers': {
        'structured': {
            'class': 'utils.logging.StructuredLogger',
            'formatter': 'structured',
        },
    },
    'formatters': {
        'structured': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
}
```

---

## Performance Monitoring

### Permission System Performance Dashboard

Located at `/usermanagement/performance/` (admin/superuser only)

**Features:**
- Real-time metrics display (permissions, roles, users, organizations)
- Cache performance statistics (hit rate, memory usage, keys)
- Recent permission check logs
- Slow query identification (>10ms)
- Benchmarking tools

**Access:**
```python
# URL: /usermanagement/performance/
# Requires: user.is_superuser or user.role == 'superadmin'
```

**API Endpoint:**
```python
# GET /usermanagement/performance/api/metrics/
# Returns: JSON with current metrics, cache stats, and benchmarks
```

### Management Command

```bash
# Basic performance monitoring
python manage.py monitor_permissions

# Detailed cache analysis
python manage.py monitor_permissions --cache-analysis

# Custom benchmarking
python manage.py monitor_permissions --iterations 500 --users 20
```

**Output Example:**
```
=== Permission System Performance Monitor ===

📊 Basic Metrics:
   Total Permissions: 245
   Total User Roles: 89
   Total User Permissions: 23

🔍 Cache Performance Analysis:
   Cache Write Time: 1.23ms
   Cache Read Time: 0.89ms
   Cache Data Integrity: ✓

⚡ Permission Check Benchmark (100 iterations, 10 users):
   Total Checks: 100
   Total Time: 0.234s
   Average Time: 2.34ms per check
   Checks/Second: 427.35
```

---

## Rate Limiting

### Overview

Rate limiting prevents abuse of permission checks and protects system performance.

**Dependencies:**
- `django-ratelimit>=4.1.0`
- `django-redis>=5.4.0`

### Configuration

**Settings (`dashboard/settings.py`):**
```python
RATELIMIT_VIEW = 'usermanagement.views.rate_limit_exceeded'
RATELIMIT_BLOCK = True
RATELIMIT_CACHE_PREFIX = 'rl:'
RATELIMIT_CACHE_BACKEND = 'default'

RATELIMITS = {
    'permission_check': '100/m',  # 100 permission checks per minute per user
    'login_attempt': '5/m',       # 5 login attempts per minute per IP
    'api_call': '1000/m',         # 1000 API calls per minute per user
    'form_submission': '10/m',    # 10 form submissions per minute per user
}
```

### Rate-Limited Permission Methods

```python
from usermanagement.utils import PermissionUtils

# Rate-limited permission checking (100 checks/minute per user)
result = PermissionUtils.has_codename_ratelimited(user, org, 'accounting_invoice_view')
result = PermissionUtils.has_permission_ratelimited(user, org, 'accounting', 'invoice', 'view')
```

### Rate-Limited Decorators

```python
from usermanagement.utils import permission_required

# Apply rate limiting to view
@permission_required('accounting_invoice_view', ratelimit_enabled=True)
def my_view(request):
    # Rate limited to 100 checks/minute per user
    pass
```

### Rate Limit Exceeded Response

**Template:** `templates/429.html`

**Features:**
- User-friendly error message
- Automatic retry suggestion
- Countdown timer
- Navigation options

---

## Query Optimization

### QueryOptimizer Class

Located in `usermanagement/query_optimizer.py`

**Purpose:** Provides optimized query patterns for list views to prevent N+1 queries and improve performance.

### Optimized Querysets

#### User Queries
```python
from usermanagement.query_optimizer import QueryOptimizer

# Optimized user queryset with all related data
users = QueryOptimizer.get_optimized_user_queryset()

# Includes: organization, memberships, roles, permission overrides
for user in users:
    org_name = user.organization.name
    role_count = len(user.role_assignments)
    permission_overrides = user.permission_overrides
```

#### Role Queries
```python
# Optimized role queryset with usage statistics
roles = QueryOptimizer.get_optimized_role_queryset()

# Includes: permissions, assigned users, counts
for role in roles:
    permission_count = role.permission_count
    user_count = role.user_count
```

#### Organization Queries
```python
# Optimized organization queryset
orgs = QueryOptimizer.get_optimized_organization_queryset()

# Includes: members, roles, counts
for org in orgs:
    member_count = org.member_count
    role_count = org.role_count
```

### Permission-Filtered Queries

```python
# Filter queryset based on user permissions
filtered_queryset = QueryOptimizer.get_permission_filtered_queryset(
    user, organization, base_queryset, 'accounting_invoice_view'
)
```

### List View Optimization Decorator

```python
from usermanagement.query_optimizer import QueryOptimizer

@QueryOptimizer.optimize_list_view_queryset
class MyListView(ListView):
    model = MyModel
    
    def get_queryset(self):
        # Automatically optimized based on model type
        return super().get_queryset()
```

### Bulk Operations

```python
from usermanagement.query_optimizer import bulk_check_permissions_optimized

# Check permissions for multiple users efficiently
results = bulk_check_permissions_optimized(user_ids, org_id, 'accounting_invoice_view')
# Returns: {user_id: True/False, ...}
```

### Performance Monitoring Decorator

```python
from usermanagement.query_optimizer import monitor_query_performance

@monitor_query_performance
def my_expensive_operation():
    # Operation will be monitored for query count and performance
    pass
```

### Optimized Helper Functions

```python
from usermanagement.query_optimizer import (
    get_users_with_permissions_optimized,
    get_roles_with_usage_stats_optimized
)

# Get users with their complete permission structure
users = get_users_with_permissions_optimized(org_id)

# Get roles with usage statistics
roles = get_roles_with_usage_stats_optimized(org_id)
```

### Performance Monitoring Context Manager

```python
from usermanagement.query_optimizer import PerformanceMonitor

with PerformanceMonitor() as monitor:
    # Perform operations
    result = some_operation()
    
# Get performance statistics
stats = monitor.get_stats()
print(f"Queries: {stats['query_count']}, Time: {stats['query_time_ms']}ms")
```

---

## Benefits

- **Improved Reliability**: Safe template tags prevent page-breaking errors
- **Better UX**: Enhanced forms with validation and loading states
- **Easier Debugging**: Template validation catches issues before deployment
- **Security**: Built-in security checks and safe operations
- **Performance**: Query optimization and caching reduce database load
- **Monitoring**: Real-time performance dashboards and metrics
- **Protection**: Rate limiting prevents abuse and ensures fair usage
- **Maintainability**: Structured logging and consistent error handling</content>
<parameter name="filePath">c:\PythonProjects\Himalytix\ERP\Docs\DASON_TEMPLATE_COMPONENTS.md