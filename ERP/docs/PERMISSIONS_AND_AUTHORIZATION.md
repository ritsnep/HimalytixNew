# Permissions and Authorization System

This document explains the complete permission and authorization system used in the Himalytix ERP application.

## Table of Contents

1. [Overview](#overview)
2. [Core Models](#core-models)
3. [Permission Structure](#permission-structure)
4. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
5. [Permission Checking Flow](#permission-checking-flow)
6. [Template Permission Checks](#template-permission-checks)
7. [View-Level Permission Enforcement](#view-level-permission-enforcement)
8. [Adding New Permissions](#adding-new-permissions)
9. [User Management](#user-management)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The system implements a **multi-tenant, organization-scoped RBAC** (Role-Based Access Control) model where:

- **Users** belong to one or more **Organizations**
- **Permissions** are granted through **Roles** assigned per organization
- **Superusers** and users with `role='superadmin'` bypass all permission checks
- Permissions are cached per (user, organization) pair for performance

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Request                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Is user.is_superuser OR user.role == 'superadmin'?             │
│  YES → FULL ACCESS (skip all checks)                            │
│  NO  → Continue to permission lookup                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Get user's active organization                                  │
│  Look up cached permissions for (user_id, organization_id)       │
│  If not cached → query Role permissions + UserPermission overrides│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  Check if required permission codename is in user's set          │
│  GRANTED → Allow access                                          │
│  DENIED  → Return 403 Forbidden                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Models

All models are defined in `usermanagement/models.py`.

### Organization

Represents a tenant/company in the multi-tenant system.

```python
class Organization(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    # ... other fields
```

### CustomUser

Extended Django user with additional fields.

```python
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ("superadmin", "Super Admin"),  # Bypasses ALL permission checks
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("accountant", "Accountant"),
        ("data_entry", "Data Entry"),
        ("user", "User"),
    ]
    
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="user")
    organization = models.ForeignKey(Organization, ...)  # Default/primary org
```

**Important:** The `role` field on `CustomUser` is a **legacy shortcut**. The actual RBAC system uses `UserRole` assignments. However, `role='superadmin'` or `is_superuser=True` grants **full access** regardless of other assignments.

### UserOrganization

Maps users to organizations they can access.

```python
class UserOrganization(models.Model):
    user = models.ForeignKey(CustomUser, ...)
    organization = models.ForeignKey(Organization, ...)
    is_owner = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    role = models.CharField(max_length=50, default='member')  # Simple role label
```

### Module

Groups related entities (e.g., "Accounting", "Inventory", "Purchasing").

```python
class Module(models.Model):
    name = models.CharField(max_length=255)       # "Accounting"
    code = models.CharField(max_length=50, unique=True)  # "accounting"
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
```

### Entity

Represents a feature/resource within a module (e.g., "SalesInvoice", "DeliveryNote").

```python
class Entity(models.Model):
    module = models.ForeignKey(Module, ...)
    name = models.CharField(max_length=255)       # "Delivery Note"
    code = models.CharField(max_length=50)        # "deliverynote"
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('module', 'code')
```

### Permission

Defines a specific action on an entity.

```python
PERMISSION_ACTION_CHOICES = [
    ('view', 'View'),
    ('add', 'Add'),
    ('change', 'Change'),
    ('delete', 'Delete'),
    ('submit', 'Submit'),
    ('approve', 'Approve'),
    ('reject', 'Reject'),
    ('post', 'Post'),
    ('reverse', 'Reverse'),
    # ... more actions
]

class Permission(models.Model):
    name = models.CharField(max_length=100)       # "Can view delivery notes"
    codename = models.CharField(max_length=100)   # "accounting_deliverynote_view"
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, ...)
    entity = models.ForeignKey(Entity, ...)
    action = models.CharField(max_length=50, choices=PERMISSION_ACTION_CHOICES)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('codename', 'module', 'entity')
```

**Codename Convention:** `{module_code}_{entity_code}_{action}`

Examples:
- `accounting_deliverynote_view`
- `accounting_deliverynote_add`
- `accounting_salesinvoice_post`
- `inventory_product_delete`

### Role

A named collection of permissions, scoped to an organization.

```python
class Role(models.Model):
    name = models.CharField(max_length=100)       # "Admin"
    code = models.CharField(max_length=50)        # "ADMIN"
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, ...)
    permissions = models.ManyToManyField(Permission, related_name='roles')
    is_system = models.BooleanField(default=False)  # True for built-in roles
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('code', 'organization')
```

**System Roles:** Created automatically for each organization:
- `ADMIN` - Full access to all permissions
- `MANAGER` - Approval and period-closing rights
- `CLERK` - Create/edit access to transactions
- `AUDITOR` - Read-only access

### UserRole

Assigns a role to a user within a specific organization.

```python
class UserRole(models.Model):
    user = models.ForeignKey(CustomUser, ...)
    role = models.ForeignKey(Role, ...)
    organization = models.ForeignKey(Organization, ...)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('user', 'role', 'organization')
```

### UserPermission

Explicit permission grants/revokes for individual users (overrides role permissions).

```python
class UserPermission(models.Model):
    user = models.ForeignKey(CustomUser, ...)
    permission = models.ForeignKey(Permission, ...)
    organization = models.ForeignKey(Organization, ...)
    is_granted = models.BooleanField(default=True)  # True=grant, False=revoke
```

---

## Permission Structure

### Hierarchical Model

```
Organization
    └── Roles (ADMIN, MANAGER, CLERK, AUDITOR, custom...)
            └── Permissions (many-to-many)
                    └── Module + Entity + Action

User
    └── UserOrganization (membership)
    └── UserRole (role assignments per org)
    └── UserPermission (explicit overrides per org)
```

### Permission Codename Format

```
{module_code}_{entity_code}_{action}
```

| Module Code | Entity Code | Action | Full Codename |
|-------------|-------------|--------|---------------|
| accounting | deliverynote | view | `accounting_deliverynote_view` |
| accounting | deliverynote | add | `accounting_deliverynote_add` |
| accounting | deliverynote | change | `accounting_deliverynote_change` |
| accounting | deliverynote | delete | `accounting_deliverynote_delete` |
| accounting | salesinvoice | post | `accounting_salesinvoice_post` |
| accounting | journal | approve_journal | `accounting_journal_approve_journal` |
| inventory | product | view | `inventory_product_view` |

---

## Role-Based Access Control (RBAC)

### System Roles

Created by `python manage.py setup_system_roles`:

| Role | Code | Description | Permissions |
|------|------|-------------|-------------|
| Admin | `ADMIN` | Full access | ALL active permissions |
| Manager | `MANAGER` | Supervisor access | View + CRUD + Approve/Reject/Post + Period closing |
| Clerk | `CLERK` | Data entry | View + Create/Edit + Submit |
| Auditor | `AUDITOR` | Read-only | View only |

### Role Permission Assignment

```python
# In setup_system_roles.py

# ADMIN gets everything
admin_role.permissions.set(all_permissions)

# CLERK gets view + basic CRUD + submit
clerk_permissions = (
    accounting_view_permissions
    | journal_crud_permissions
    | clerk_extra_permissions
    | purchasing_view_permissions
    | purchasing_edit_permissions
)
clerk_role.permissions.set(clerk_permissions)

# MANAGER gets clerk permissions + approval + period management
manager_permissions = (
    clerk_permissions
    | manager_special_permissions  # approve, reject, post, close_period, etc.
)
manager_role.permissions.set(manager_permissions)

# AUDITOR gets view only
auditor_role.permissions.set(auditor_permissions | purchasing_view_permissions)
```

---

## Permission Checking Flow

### Core Utility: `PermissionUtils`

Located in `usermanagement/utils.py`:

```python
class PermissionUtils:
    CACHE_TIMEOUT = 900  # Increased to 15 minutes
    CACHE_VERSION = 1  # Add versioning for cache busting
    logger = StructuredLogger('permissions')

    @staticmethod
    def _cache_key(user_id, organization_id):
        """Versioned cache key to enable global invalidation."""
        return f'user_permissions:v{PermissionUtils.CACHE_VERSION}:{user_id}:{organization_id}'

    @staticmethod
    def get_user_permissions(user, organization):
        """Get permissions with fallback on cache failure."""
        # Superuser check
        if not user or not getattr(user, 'is_authenticated', False):
            return set()

        if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
            return {'*'}  # Use set instead of list

        if not organization:
            return set()

        cache_key = PermissionUtils._cache_key(user.id, organization.id)

        try:
            permissions = cache.get(cache_key)
            if permissions is not None:
                return permissions
        except Exception as e:
            # Log but don't fail - fall through to DB query
            logger.warning(f"Cache read failed for {cache_key}: {e}")

        # Query permissions (existing logic)
        permissions = PermissionUtils._query_permissions(user, organization)

        # Try to cache, but don't fail if it doesn't work
        try:
            cache.set(cache_key, permissions, PermissionUtils.CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Cache write failed for {cache_key}: {e}")

        return permissions

    @staticmethod
    def _query_permissions(user, organization):
        """Separate method for DB query logic."""
        role_permissions = set(
            Permission.objects.filter(
                roles__user_roles__user=user,
                roles__user_roles__organization=organization,
                roles__user_roles__is_active=True,
                roles__is_active=True,
                is_active=True,
            ).values_list('codename', flat=True)
        )

        # Apply overrides with select_related to reduce queries
        overrides = UserPermission.objects.filter(
            user=user,
            organization=organization,
        ).select_related('permission')

        for override in overrides:
            codename = override.permission.codename
            if override.is_granted:
                role_permissions.add(codename)
            else:
                role_permissions.discard(codename)

        return role_permissions

    @staticmethod
    def invalidate_user_cache(user_id, organization_id):
        """Invalidate specific user cache."""
        cache.delete(PermissionUtils._cache_key(user_id, organization_id))

    @staticmethod
    def invalidate_all_caches():
        """Global cache bust by incrementing version."""
        PermissionUtils.CACHE_VERSION += 1
        # Persist version to settings or database if needed

    @staticmethod
    def bulk_invalidate(user_ids, organization_id):
        """Efficiently invalidate multiple users."""
        keys = [PermissionUtils._cache_key(uid, organization_id) for uid in user_ids]
        cache.delete_many(keys)

    @staticmethod
    def has_codename(user, organization, permission_codename: str):
        """Check a permission codename against the scoped Role/Permission matrix."""
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "role", None) == "superadmin" or getattr(user, "is_superuser", False):
            return True

        if permission_codename and "." in permission_codename:
            return user.has_perm(permission_codename)

        if not organization:
            return False

        permissions = PermissionUtils.get_user_permissions(user, organization)
        if permissions == {'*'}:  # Handle super admin case
            return True

        return permission_codename in permissions

    @staticmethod
    def has_permission(user, organization, module, entity, action):
        codename = f"{module}_{entity}_{action}"
        granted = PermissionUtils.has_codename(user, organization, codename)

        PermissionUtils.logger.log_permission_check(
            user, organization, codename, granted
        )

        return granted

    @staticmethod
    def invalidate_cache(user_id, organization_id):
        """Invalidate specific user cache. (Legacy method for backward compatibility)"""
        PermissionUtils.invalidate_user_cache(user_id, organization_id)
```

### Cache Invalidation

**When to invalidate:**
- After assigning/removing a user from a role
- After changing a role's permissions
- After adding/removing UserPermission overrides

```python
from usermanagement.utils import PermissionUtils

# Invalidate for a specific user/org
PermissionUtils.invalidate_user_cache(user.id, organization.id)

# Bulk invalidate for multiple users
PermissionUtils.bulk_invalidate(user_ids, organization_id)

# Global cache bust (increments version, invalidates all caches)
PermissionUtils.invalidate_all_caches()
```

### Cache Versioning

The system uses **cache versioning** to enable global cache invalidation:

```python
class PermissionUtils:
    CACHE_TIMEOUT = 900  # Increased to 15 minutes
    CACHE_VERSION = 1    # Global version for cache busting
    
    @staticmethod
    def _cache_key(user_id, organization_id):
        return f'user_permissions:v{PermissionUtils.CACHE_VERSION}:{user_id}:{organization_id}'
```

When `invalidate_all_caches()` is called, it increments `CACHE_VERSION`, making all existing cache keys invalid.

### Error Handling

The permission system includes robust error handling:

```python
@staticmethod
def get_user_permissions(user, organization):
    # ... existing logic ...
    
    try:
        permissions = cache.get(cache_key)
        if permissions is not None:
            return permissions
    except Exception as e:
        # Log but don't fail - fall through to DB query
        logger.warning(f"Cache read failed for {cache_key}: {e}")
    
    # Query permissions (existing logic)
    permissions = PermissionUtils._query_permissions(user, organization)
    
    # Try to cache, but don't fail if it doesn't work
    try:
        cache.set(cache_key, permissions, PermissionUtils.CACHE_TIMEOUT)
    except Exception as e:
        logger.warning(f"Cache write failed for {cache_key}: {e}")
    
    return permissions
```

---

## Rate Limiting

### Overview

Rate limiting prevents abuse of permission checks and protects system performance by limiting how many permission operations a user can perform within a time window.

**Dependencies:**
- `django-ratelimit>=4.1.0`
- `django-redis>=5.4.0`

### Configuration

**Settings (`dashboard/settings.py`):**
```python
RATELIMIT_VIEW = 'usermanagement.views.rate_limit_exceeded'
RATELIMIT_BLOCK = True  # Block requests that exceed limits
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

# Standard permission checking (no rate limit)
result = PermissionUtils.has_codename(user, org, 'accounting_invoice_view')

# Rate-limited permission checking (100 checks/minute per user)
result = PermissionUtils.has_codename_ratelimited(user, org, 'accounting_invoice_view')
result = PermissionUtils.has_permission_ratelimited(user, org, 'accounting', 'invoice', 'view')
```

### Rate-Limited Decorators

```python
from usermanagement.utils import permission_required

# Standard permission check
@permission_required('accounting_invoice_view')
def my_view(request):
    pass

# Rate-limited permission check (100 checks/minute per user)
@permission_required('accounting_invoice_view', ratelimit_enabled=True)
def my_rate_limited_view(request):
    pass
```

### Rate Limit Exceeded Response

When rate limits are exceeded, users see a user-friendly error page (`templates/429.html`) with:

- Clear error message explaining the limit
- Automatic retry suggestion after cooldown period
- Navigation options to return to dashboard
- Countdown timer for when they can retry

---

## Performance Monitoring

### Permission System Performance Dashboard

**URL:** `/usermanagement/performance/` (admin/superuser only)

**Features:**
- **Real-time Metrics:** Total permissions, roles, users, organizations
- **Cache Performance:** Hit rate, memory usage, key count, hits/misses
- **Recent Activity:** Permission check logs with timing
- **Slow Query Detection:** Identifies queries taking >10ms
- **Benchmarking Tools:** Run performance tests on-demand

**Access Requirements:**
```python
# Requires superuser or superadmin role
user.is_superuser or getattr(user, 'role', None) == 'superadmin'
```

### API Endpoint

**URL:** `/usermanagement/performance/api/metrics/`

**Response:**
```json
{
  "timestamp": 1703123456.789,
  "metrics": {
    "total_permissions": 245,
    "total_user_roles": 89,
    "total_user_permissions": 23,
    "active_users": 42,
    "total_organizations": 5
  },
  "cache": {
    "backend": "redis",
    "keys": 1250,
    "hit_rate": 94.2,
    "hits": 15420,
    "misses": 950,
    "memory_usage": "2.4MB"
  },
  "benchmarks": {
    "permission_check_time_ms": 2.34,
    "cache_operation_time_ms": 0.89,
    "queries_per_check": 1
  },
  "health_status": "healthy"
}
```

### Management Command

```bash
# Basic performance monitoring
python manage.py monitor_permissions

# Detailed cache analysis with custom parameters
python manage.py monitor_permissions --cache-analysis --iterations 500 --users 20

# Output example:
# 📊 Basic Metrics:
#    Total Permissions: 245
#    Total User Roles: 89
#    Total User Permissions: 23
#
# ⚡ Permission Check Benchmark (100 iterations, 10 users):
#    Total Checks: 100
#    Total Time: 0.234s
#    Average Time: 2.34ms per check
#    Checks/Second: 427.35
```

---

## Query Optimization

### QueryOptimizer Class

Located in `usermanagement/query_optimizer.py`

**Purpose:** Provides optimized query patterns for list views to prevent N+1 queries and improve performance.

### Optimized Querysets

#### User Queries with Related Data
```python
from usermanagement.query_optimizer import QueryOptimizer

# Optimized user queryset with all related data pre-fetched
users = QueryOptimizer.get_optimized_user_queryset()

# Includes: organization, memberships, roles, permission overrides
for user in users:
    org_name = user.organization.name  # No additional query
    role_count = len(user.role_assignments)  # Pre-fetched
    permission_overrides = user.permission_overrides  # Pre-fetched
```

#### Role Queries with Statistics
```python
# Optimized role queryset with usage statistics
roles = QueryOptimizer.get_optimized_role_queryset()

# Includes: permissions, assigned users, and counts
for role in roles:
    permission_count = role.permission_count  # Annotated
    user_count = role.user_count  # Annotated
```

#### Organization Queries
```python
# Optimized organization queryset
orgs = QueryOptimizer.get_optimized_organization_queryset()

# Includes: members, roles, and counts
for org in orgs:
    member_count = org.member_count  # Annotated
    role_count = org.role_count  # Annotated
```

### Permission-Filtered Queries

```python
# Filter queryset based on user permissions
from usermanagement.query_optimizer import QueryOptimizer

filtered_queryset = QueryOptimizer.get_permission_filtered_queryset(
    user, organization, base_queryset, 'accounting_invoice_view'
)
```

### List View Optimization Decorator

```python
from usermanagement.query_optimizer import QueryOptimizer

@QueryOptimizer.optimize_list_view_queryset
class UserListView(ListView):
    model = CustomUser
    
    def get_queryset(self):
        # Automatically optimized with select_related/prefetch_related
        # and permission filtering based on model type
        return super().get_queryset()
```

### Bulk Permission Checking

```python
from usermanagement.query_optimizer import bulk_check_permissions_optimized

# Check permissions for multiple users efficiently (single query)
results = bulk_check_permissions_optimized(
    user_ids=[1, 2, 3, 4, 5], 
    org_id=1, 
    permission_codename='accounting_invoice_view'
)
# Returns: {1: True, 2: False, 3: True, 4: False, 5: True}
```

### Performance Monitoring

```python
from usermanagement.query_optimizer import monitor_query_performance, PerformanceMonitor

@monitor_query_performance
def my_expensive_operation():
    # Operation will be logged with query count and timing
    pass

# Context manager for detailed monitoring
with PerformanceMonitor() as monitor:
    # Perform operations
    result = some_operation()
    
# Get detailed statistics
stats = monitor.get_stats()
# {
#     'query_count': 3,
#     'query_time_ms': 45.67,
#     'cache_hits': 2,
#     'cache_misses': 1,
#     'cache_hit_rate': 66.67
# }
```

### Optimized Helper Functions

```python
from usermanagement.query_optimizer import (
    get_users_with_permissions_optimized,
    get_roles_with_usage_stats_optimized
)

# Get users with complete permission structure (optimized)
users = get_users_with_permissions_optimized(org_id)

# Get roles with usage statistics (optimized)
roles = get_roles_with_usage_stats_optimized(org_id)
```

---

## Template Permission Checks

### Template Tag: `has_permission`

Located in `usermanagement/templatetags/permission_tags.py`:

```python
@register.filter(name='has_permission')
def has_permission_filter(user, permission_string):
    """
    Usage: {% if user|has_permission:'accounting_deliverynote_view' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superuser/superadmin always passes
    if getattr(user, 'role', None) == 'superadmin' or getattr(user, 'is_superuser', False):
        return True

    module, entity, action = _parse_permission_string(permission_string)
    return PermissionUtils.has_permission(
        user,
        user.get_active_organization(),
        module,
        entity,
        action,
    )
```

### Using in Templates

```django
{% load permission_tags %}

{# Check single permission #}
{% if user|has_permission:'accounting_deliverynote_view' %}
    <li><a href="{% url 'accounting:delivery_note_list' %}">Delivery Notes</a></li>
{% endif %}

{# Safe URL resolution pattern (prevents NoReverseMatch errors) #}
{% if user|has_permission:'accounting_deliverynote_view' %}
    {% url 'accounting:delivery_note_list' as delivery_notes_url %}
    {% if delivery_notes_url %}
        <li><a href="{{ delivery_notes_url }}">Delivery Notes</a></li>
    {% endif %}
{% endif %}
```

### Sidebar Menu Example

From `templates/partials/left-sidebar.html`:

```django
{% load permission_tags %}

<!-- Billing Section -->
<li>
    <a href="javascript: void(0);" class="has-arrow">
        <i data-feather="credit-card"></i>
        <span>Billing</span>
    </a>
    <ul class="sub-menu" aria-expanded="false">
        {% if user|has_permission:'accounting_salesorder_view' %}
        <li>
            <a href="{% url 'accounting:sales_order_list' %}">
                <i class="fas fa-shopping-bag"></i>
                <span>Sales Orders</span>
            </a>
        </li>
        {% endif %}
        
        {% if user|has_permission:'accounting_deliverynote_view' %}
        {% url 'accounting:delivery_note_list' as delivery_notes_url %}
        {% if delivery_notes_url %}
        <li>
            <a href="{{ delivery_notes_url }}">
                <i class="fas fa-truck"></i>
                <span>Delivery Notes</span>
            </a>
        </li>
        {% endif %}
        {% endif %}
        
        {% if user|has_permission:'accounting_salesinvoice_view' %}
        <li>
            <a href="{% url 'accounting:sales_invoice_list' %}">
                <i class="fas fa-file-invoice"></i>
                <span>Sales Invoices</span>
            </a>
        </li>
        {% endif %}
    </ul>
</li>
```

---

## View-Level Permission Enforcement

### Mixin: `PermissionRequiredMixin`

Located in `accounting/mixins.py`:

```python
class PermissionRequiredMixin:
    """
    Mixin for class-based views that require a specific permission.
    
    Usage:
        class MyView(PermissionRequiredMixin, View):
            permission_required = ('accounting', 'deliverynote', 'view')
    """
    permission_required = None  # Tuple: (module, entity, action)

    def get_organization(self):
        """Get the current user's active organization."""
        return getattr(self.request, 'organization', None) or \
               self.request.user.get_active_organization()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        organization = self.get_organization()
        if not organization:
            messages.warning(request, "Please select an organization.")
            return redirect('usermanagement:select_organization')
        
        if self.permission_required:
            module, entity, action = self.permission_required
            if not PermissionUtils.has_permission(request.user, organization, module, entity, action):
                messages.error(request, "You don't have permission to access this page.")
                return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
```

### Using in Views

```python
from accounting.mixins import PermissionRequiredMixin

class DeliveryNoteListView(PermissionRequiredMixin, ListView):
    model = DeliveryNote
    template_name = "accounting/delivery_note_list.html"
    permission_required = ("accounting", "deliverynote", "view")

class DeliveryNoteCreateView(PermissionRequiredMixin, View):
    permission_required = ("accounting", "deliverynote", "add")
    # ...

class DeliveryNotePrintView(PermissionRequiredMixin, DetailView):
    permission_required = ("accounting", "deliverynote", "view")
    # ...
```

### Decorator: `@permission_required`

For function-based views:

```python
from usermanagement.utils import permission_required

@permission_required(('accounting', 'deliverynote', 'view'))
def delivery_note_list(request):
    # ...
```

---

## Adding New Permissions

### Step 1: Update Permission Bootstrap Command

Edit `usermanagement/management/commands/setup_permissions.py`:

```python
# Add entity definition
ENTITY_DEFINITIONS = [
    # ... existing entities
    {
        'module': 'accounting',
        'code': 'deliverynote',
        'name': 'Delivery Note',
        'description': 'Delivery note/challan management',
    },
]

# Add permission definitions
PERMISSION_DEFINITIONS = [
    # ... existing permissions
    {
        'module': 'accounting',
        'entity': 'deliverynote',
        'action': 'view',
        'name': 'Can view delivery notes',
        'description': 'Allows viewing delivery notes and challans.',
    },
    {
        'module': 'accounting',
        'entity': 'deliverynote',
        'action': 'add',
        'name': 'Can add delivery notes',
        'description': 'Allows creating new delivery notes.',
    },
    {
        'module': 'accounting',
        'entity': 'deliverynote',
        'action': 'change',
        'name': 'Can change delivery notes',
        'description': 'Allows editing delivery notes.',
    },
    {
        'module': 'accounting',
        'entity': 'deliverynote',
        'action': 'delete',
        'name': 'Can delete delivery notes',
        'description': 'Allows deleting delivery notes.',
    },
]
```

### Step 2: Run Permission Setup

```bash
python manage.py setup_permissions
```

### Step 3: Assign to Roles

Run the system roles setup to assign new permissions to the ADMIN role:

```bash
python manage.py setup_system_roles
```

This automatically:
- Creates/updates system roles for all organizations
- Assigns ALL permissions to ADMIN role
- Assigns appropriate subsets to other roles

### Step 4: Invalidate Caches

For immediate effect without user re-login:

```python
from usermanagement.models import UserOrganization
from usermanagement.utils import PermissionUtils

# Invalidate all user caches for an organization
for uo in UserOrganization.objects.filter(organization=org):
    PermissionUtils.invalidate_cache(uo.user.id, uo.organization.id)
```

---

## User Management

### Creating a New User with Permissions

```python
from usermanagement.models import CustomUser, Organization, UserOrganization, Role, UserRole

# 1. Create user
user = CustomUser.objects.create_user(
    username='john.doe',
    email='john@example.com',
    password='securepassword',
    full_name='John Doe',
    role='user',  # Legacy field, not used for RBAC
)

# 2. Associate with organization
org = Organization.objects.get(code='ACME')
UserOrganization.objects.create(
    user=user,
    organization=org,
    is_active=True,
    role='member',
)

# 3. Assign role
clerk_role = Role.objects.get(code='CLERK', organization=org)
UserRole.objects.create(
    user=user,
    role=clerk_role,
    organization=org,
    is_active=True,
)
```

### Granting Extra Permissions to a User

```python
from usermanagement.models import Permission, UserPermission

# Grant a specific permission to a user (override role)
perm = Permission.objects.get(codename='accounting_journal_approve_journal')
UserPermission.objects.create(
    user=user,
    permission=perm,
    organization=org,
    is_granted=True,  # True = grant, False = revoke
)

# Invalidate cache
PermissionUtils.invalidate_cache(user.id, org.id)
```

### Revoking a Permission

```python
# Revoke a permission that would otherwise be granted by role
UserPermission.objects.create(
    user=user,
    permission=perm,
    organization=org,
    is_granted=False,  # Explicitly revoke
)

PermissionUtils.invalidate_cache(user.id, org.id)
```

---

## Troubleshooting

### Permission Not Working - Checklist

1. **Is the user a superuser?**
   ```python
   user.is_superuser  # If True, bypasses all checks
   user.role  # If 'superadmin', bypasses all checks
   ```

2. **Does the permission exist in the database?**
   ```python
   from usermanagement.models import Permission
   Permission.objects.filter(codename__icontains='deliverynote').values_list('codename', flat=True)
   ```

3. **Is the user assigned to the correct organization?**
   ```python
   user.get_active_organization()
   UserOrganization.objects.filter(user=user, is_active=True)
   ```

4. **Is the user assigned to a role in that organization?**
   ```python
   UserRole.objects.filter(user=user, organization=org, is_active=True)
   ```

5. **Does the role have the permission?**
   ```python
   role = UserRole.objects.get(user=user, organization=org).role
   role.permissions.filter(codename='accounting_deliverynote_view').exists()
   ```

6. **Is there a UserPermission override revoking it?**
   ```python
   UserPermission.objects.filter(
       user=user,
       organization=org,
       permission__codename='accounting_deliverynote_view',
       is_granted=False,
   ).exists()
   ```

7. **Is the permission cache stale?**
   ```python
   PermissionUtils.invalidate_cache(user.id, org.id)
   ```

### Debug Script

Save as `scripts/debug_user_permissions.py`:

```python
#!/usr/bin/env python
"""Debug a user's permissions."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp.settings')

import django
django.setup()

from usermanagement.models import CustomUser, UserOrganization, UserRole, Permission
from usermanagement.utils import PermissionUtils


def debug_user(username):
    try:
        user = CustomUser.objects.get(username=username)
    except CustomUser.DoesNotExist:
        print(f"User '{username}' not found")
        return

    print(f"=== User: {user.username} ===")
    print(f"is_superuser: {user.is_superuser}")
    print(f"role: {user.role}")
    print(f"is_active: {user.is_active}")
    
    org = user.get_active_organization()
    print(f"\nActive Organization: {org.name if org else 'None'}")
    
    print("\n=== Organization Memberships ===")
    for uo in UserOrganization.objects.filter(user=user):
        print(f"  - {uo.organization.name}: role={uo.role}, active={uo.is_active}")
    
    print("\n=== Role Assignments ===")
    for ur in UserRole.objects.filter(user=user).select_related('role', 'organization'):
        perm_count = ur.role.permissions.count()
        print(f"  - {ur.role.name} in {ur.organization.name}: {perm_count} permissions, active={ur.is_active}")
    
    if org:
        print(f"\n=== Effective Permissions in {org.name} ===")
        perms = PermissionUtils.get_user_permissions(user, org)
        if perms == ['*']:
            print("  FULL ACCESS (superuser/superadmin)")
        else:
            print(f"  Total: {len(perms)} permissions")
            # Show deliverynote permissions
            dn_perms = [p for p in sorted(perms) if 'deliverynote' in p]
            if dn_perms:
                print(f"  Delivery Note permissions: {dn_perms}")


if __name__ == '__main__':
    username = sys.argv[1] if len(sys.argv) > 1 else 'admin'
    debug_user(username)
```

Run with:
```bash
python manage.py shell < scripts/debug_user_permissions.py
# Or
python scripts/debug_user_permissions.py admin
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Menu item not visible | Permission not assigned to user's role | Run `setup_system_roles` or manually add permission to role |
| 403 Forbidden on view | User lacks required permission | Check `permission_required` tuple matches DB codename |
| Permission exists but not granted | Cache is stale | Call `PermissionUtils.invalidate_cache(user_id, org_id)` |
| New permission not in DB | Bootstrap not run | Run `python manage.py setup_permissions` |
| URL not found error | URL not registered | Check `accounting/urls/__init__.py` (not `urls.py`) |

---

## File Reference

| File | Purpose |
|------|---------|
| `usermanagement/models.py` | Core models (Organization, CustomUser, Role, Permission, etc.) |
| `usermanagement/utils.py` | PermissionUtils class and decorators |
| `usermanagement/templatetags/permission_tags.py` | Template filters and tags |
| `usermanagement/management/commands/setup_permissions.py` | Creates Module, Entity, Permission records |
| `usermanagement/management/commands/setup_system_roles.py` | Creates system roles and assigns permissions |
| `accounting/mixins.py` | PermissionRequiredMixin for views |
| `accounting/urls/__init__.py` | URL patterns (note: this is the active file, not `urls.py`) |
| `templates/partials/left-sidebar.html` | Navigation menu with permission checks |

---

## Summary

1. **Permissions** are defined as `module_entity_action` codenames
2. **Roles** group permissions and are scoped per organization
3. **Users** get permissions through **UserRole** assignments
4. **UserPermission** allows explicit grants/revokes overriding role permissions
5. **Superusers** (`is_superuser=True`) and **superadmins** (`role='superadmin'`) bypass all checks
6. **Caching** improves performance but requires manual invalidation on changes
7. **Template checks** use `{% if user|has_permission:'codename' %}`
8. **View checks** use `PermissionRequiredMixin` with `permission_required` tuple
