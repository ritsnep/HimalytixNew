# Performance Optimizations Applied

This document summarizes practical changes and safe recommendations to make your Django app faster. Any timing numbers here are estimates; please measure on your machine using the quick tests below.

## Problem: App was very slow (25+ seconds per page load)

### Root Causes Identified:

1. **DEBUG = True** - Causes Django to track all queries in memory
2. **No Template Caching** - Templates recompiled on every request
3. **Silk Profiler Running** - SQL profiling adds significant overhead
4. **N+1 Query Problems** - Multiple unnecessary database queries
5. **Inefficient Statistics Calculation** - Loading all records into memory

---

## Optimizations Applied:

### 1. ✅ Template Caching Enabled
**File:** `dashboard/settings.py`

**Change:**
```python
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            ...
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
            ] if not DEBUG else None,
        },
    },
]
```

**Impact:** Templates are cached in memory, avoiding recompilation on every request.

Note: When `'OPTIONS.loaders'` is set, Django ignores `APP_DIRS` (it can remain `True` without harm). The cached loader wraps the filesystem and app directory loaders.

---

### 2. ✅ Disabled Silk Profiler in Production
**File:** `dashboard/settings.py`

**Change:**
```python
MIDDLEWARE = [
    # 'silk.middleware.SilkyMiddleware',  # <-- DISABLED
    ...
]
```

**Impact:** Removes SQL profiling overhead from every request. Re-enable only when debugging SQL queries.

To temporarily re-enable Silk for profiling:

```python
MIDDLEWARE = [
    'silk.middleware.SilkyMiddleware',  # enable temporarily for local profiling
    # ... keep it early in the stack
]
```

Then visit `/silk/` locally, profile, and disable again when done.

---

### 3. ✅ Optimized Journal List Statistics
**File:** `accounting/views/voucher_list_view.py`

**Before (6 queries + loading all records):**
```python
all_journals = Journal.objects.filter(organization=organization)
statistics = {
    'total': all_journals.count(),                              # Query 1
    'draft': all_journals.filter(status='draft').count(),       # Query 2
    'pending': all_journals.filter(status='pending').count(),   # Query 3
    'posted': all_journals.filter(status='posted').count(),     # Query 4
    'approved': all_journals.filter(status='approved').count(), # Query 5
    'total_amount': sum(j.total_debit for j in all_journals),   # Query 6 - LOADS ALL!
}
```

**After (1 aggregation query):**
```python
statistics = all_journals.aggregate(
    total=Count('id'),
    draft=Count('id', filter=Q(status='draft')),
    pending=Count('id', filter=Q(status='pending')),
    posted=Count('id', filter=Q(status='posted')),
    approved=Count('id', filter=Q(status='approved')),
    total_amount=Sum('total_debit')
)
```

**Impact:** Reduced from 6 database queries to 1 efficient aggregation. Eliminates loading all journal records into memory.

---

### 4. ✅ Removed Unnecessary .count() Calls
**File:** `accounting/views/voucher_list_view.py`

**Change:** Removed `queryset.count()` from debug logging in `get_queryset()`

**Impact:** Eliminates an extra COUNT query on every page load.

---

### 5. ✅ Reused QuerySet in Context
**File:** `accounting/views/voucher_list_view.py`

**Before:**
```python
queryset_totals = self.get_queryset().aggregate(...)  # Re-queries database
```

**After:**
```python
queryset_totals = context['object_list'].aggregate(...)  # Reuses existing queryset
```

**Impact:** Avoids duplicate queries.

---

## Additional Recommendations:

### For Production Deployment:

1. **Set DEBUG = False**
   ```python
   DEBUG = False
   ```

2. **Add Database Indexing**
   - `journal_date` - for date range queries
   - `status` - for status filtering
   - `organization_id` - already exists (FK)
   - `journal_type_id` - already exists (FK)
   - Composite index on `(organization_id, journal_date, status)` for common queries

3. **Enable Query Result Caching**
   - Cache journal statistics for 5 minutes
   - Cache accounting periods list
   - Cache journal types list

4. **Database Connection Pooling**
   - Already configured with `CONN_MAX_AGE = 600`
   - Consider using PgBouncer for PostgreSQL

5. **Redis Caching**
   - Already configured
   - Use for frequently accessed data

6. **Pagination Optimization**
   - Current: 25 items per page (good)
   - Consider using cursor-based pagination for very large datasets

---

## Expected Performance Improvements (estimates)

Results vary by dataset, machine, and network. Typical improvements after these changes:

- Template loading: noticeably faster with caching
- Journal list page: dramatically faster when aggregation replaces per-status counts and full-table loads
- Statistics calculation: significantly faster (single aggregation vs multiple counts)
- Overall response time: measurable reduction; verify with the tests below

---

## Testing Performance

### Using Django Silk (when enabled):
1. Uncomment Silk middleware
2. Visit `/silk/` to see query profiling
3. Identify slow queries
4. Add select_related/prefetch_related as needed

### Using Django Debug Toolbar (alternative):
```python
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']
```

### Database Query Optimization:

Windows (PowerShell) notes:

- Run from your project folder (for you: `C:\PythonProjects\Himalytix\erp`).
- Use the bundled `curl.exe` (Windows 10+ includes it). If PowerShell aliases interfere, call `curl.exe` explicitly:

```powershell
- Use `select_related()` for ForeignKey relationships (already done)
- Use `prefetch_related()` for reverse FKs and M2M (already done)
- Use `.only()` to fetch specific fields
- Use `.defer()` to exclude heavy fields

---

## Testing Performance:

```bash
# Before optimization
curl -w "@curl-format.txt" -s http://localhost:8000/accounting/journals/

# After optimization (should be much faster)
```

Create `curl-format.txt`:
```
time_namelookup:  %{time_namelookup}s\n
time_connect:  %{time_connect}s\n
time_starttransfer:  %{time_starttransfer}s\n
time_total:  %{time_total}s\n
```

---

## Next Steps:

1. ✅ Template caching enabled
2. ✅ Silk profiler disabled
3. ✅ Query optimization applied
4. ⏳ Test performance improvement
5. ⏳ Add database indexes (see migrations below)
6. ⏳ Consider query result caching

---

## Database Index Migration (Recommended):

Create new migration file (run from `C:\PythonProjects\Himalytix\erp`):
```bash
python manage.py makemigrations accounting --empty -n add_performance_indexes
```

Add to migration:
```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0102_alter_fiscalyear_id'),
    ]

    operations = [
        # Composite index for common journal queries
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(
                fields=['organization', 'journal_date', 'status'],
                name='journal_org_date_status_idx'
            ),
        ),
        # Index for date range filtering
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(
                fields=['journal_date'],
                name='journal_date_idx'
            ),
        ),
        # Index for status filtering
        migrations.AddIndex(
            model_name='journal',
            index=models.Index(
                fields=['status'],
                name='journal_status_idx'
            ),
        ),
    ]
```

Then run the migration:
```bash
python manage.py migrate
```
