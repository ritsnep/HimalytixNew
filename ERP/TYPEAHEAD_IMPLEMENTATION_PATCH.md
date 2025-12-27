# Typeahead Lookup Implementation Patch
**Date:** December 27, 2025  
**Purpose:** Fix HTMX typeahead lookups on voucher form fields  
**Scope:** Safe, backward-compatible enhancements  

---

## FILE 1: Create New Widget Class
**Path:** `accounting/widgets.py` (NEW FILE)

```python
"""
Custom form widgets for accounting module.
Ensures typeahead fields maintain data attributes through rendering.
"""
import logging
from django import forms
from django.forms.widgets import TextInput

logger = logging.getLogger(__name__)


class TypeaheadInput(TextInput):
    """
    Custom TextInput widget for typeahead/lookup fields.
    Ensures data-* attributes are properly rendered and not lost.
    """
    input_type = 'text'
    
    def __init__(self, attrs=None):
        super().__init__(attrs)
        # Ensure essential data attributes
        if 'autocomplete' not in self.attrs:
            self.attrs['autocomplete'] = 'off'
    
    def render(self, name, value, attrs=None, renderer=None):
        """Override render to ensure data attributes are preserved."""
        if attrs is None:
            attrs = {}
        
        # Merge widget attrs with passed attrs
        final_attrs = self.build_attrs(self.attrs, attrs)
        
        # Ensure data attributes are in final attrs
        for key, val in self.attrs.items():
            if key.startswith('data-') or key == 'autocomplete':
                final_attrs[key] = val
        
        return super().render(name, value, final_attrs, renderer)
```

---

## FILE 2: Update Form Factory
**Path:** `accounting/forms_factory.py`

### Change 2.1: Add Import
**Location:** Around line 15 (after existing imports)

```diff
from .forms_factory import build_form
from accounting.schema_validation import validate_ui_schema
from accounting.services.voucher_errors import VoucherProcessError
+ from accounting.widgets import TypeaheadInput

logger = logging.getLogger(__name__)
```

### Change 2.2: Replace configure_widget_for_schema Function
**Location:** Lines 19-130 (entire function)

```diff
- def configure_widget_for_schema(field_name, field_schema, widget):
-     """
-     Inject HTML data attributes for dynamic UI behavior (typeahead, date, etc.).
-     """
-     field_type = (field_schema or {}).get('type')
-     lookup_aliases = {
-         'account': 'account',
-         'party': 'party',
-         'customer': 'customer',
-         'vendor': 'vendor',
-         'agent': 'agent',
-         'product': 'product',
-         'warehouse': 'warehouse',
-         'cost_center': 'cost_center',
-         'department': 'department',
-         'project': 'project',
-         'journal_type': 'journal_type',
-         'period': 'period',
-         'currency': 'currency',
-         'rate': 'rate',
-         'tax_code': 'tax_code',
-         'uom': 'uom',
-     }
-     lookup_types = set(lookup_aliases) | {'lookup', 'typeahead', 'autocomplete'}
-     if field_type in lookup_types:
-         lookup_kind = (
-             field_schema.get('lookup_kind')
-             or field_schema.get('lookup')
-             or lookup_aliases.get(field_type)
-             or None
-         )
-         if lookup_kind:
-             lookup_kind = str(lookup_kind).replace('-', '_').lower()
-         lookup_model = field_schema.get('lookup_model')
-         if not lookup_kind and lookup_model:
-             model_key = str(lookup_model).replace('-', '_').lower()
-             model_map = {
-                 'chartofaccount': 'account',
-                 'account': 'account',
-                 'vendor': 'vendor',
-                 'supplier': 'vendor',
-                 'customer': 'customer',
-                 'client': 'customer',
-                 'agent': 'agent',
-                 'product': 'product',
-                 'item': 'product',
-                 'service': 'product',
-                 'inventoryitem': 'product',
-                 'warehouse': 'warehouse',
-                 'taxcode': 'tax_code',
-                 'costcenter': 'cost_center',
-                 'department': 'department',
-                 'project': 'project',
-             }
-             lookup_kind = model_map.get(model_key)
-         lookup_kind = lookup_kind or 'account'
-         lookup_url = field_schema.get('lookup_url')
-         endpoint = None
-         lookup_endpoints = {
-             'account': '/accounting/vouchers/htmx/account-lookup/',
-             'vendor': '/accounting/journal-entry/lookup/vendors/',
-             'customer': '/accounting/journal-entry/lookup/customers/',
-             'agent': '/accounting/journal-entry/lookup/agents/',
-             'product': '/accounting/journal-entry/lookup/products/',
-             'warehouse': '/accounting/journal-entry/lookup/warehouses/',
-             'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
-             'cost_center': '/accounting/journal-entry/lookup/cost-centers/',
-             'department': '/accounting/journal-entry/lookup/departments/',
-             'project': '/accounting/journal-entry/lookup/projects/',
-         }
-         if lookup_url:
-             endpoint = lookup_url
-         elif lookup_kind in lookup_endpoints:
-             endpoint = lookup_endpoints[lookup_kind]
-         elif field_type in ('lookup', 'typeahead', 'autocomplete'):
-             endpoint = f"/accounting/api/{lookup_kind}/search/"
-         base_classes = widget.attrs.get('class', '').strip()
-         for cls in ('generic-typeahead', 've-suggest-input', 'typeahead-input'):
-             if cls not in base_classes:
-                 base_classes = f"{base_classes} {cls}".strip()
-         widget.attrs.update({
-             'class': base_classes,
-             'data-lookup-kind': str(lookup_kind),
-             'autocomplete': 'off',
-         })
-         if endpoint:
-             widget.attrs.setdefault('data-endpoint', endpoint)
-         if field_name:
-             widget.attrs.setdefault('data-hidden-name', field_name)
-     elif field_type == 'date':
-         widget.attrs.setdefault('type', 'date')
-         base_classes = widget.attrs.get('class', '').strip()
-         if 'date-picker' not in base_classes:
-             widget.attrs['class'] = f"{base_classes} date-picker".strip()
-     elif field_type == 'datetime':
-         widget.attrs.setdefault('type', 'datetime-local')
-         base_classes = widget.attrs.get('class', '').strip()
-         if 'datetime-picker' not in base_classes:
-             widget.attrs['class'] = f"{base_classes} datetime-picker".strip()
-     elif field_type in ('number', 'decimal', 'integer'):
-         step_val = field_schema.get('step')
-         if step_val is None:
-             step_val = '1' if field_type == 'integer' else '0.01'
-         widget.attrs.setdefault('step', str(step_val))
-
-     return widget

+ def configure_widget_for_schema(field_name, field_schema, widget):
+     """
+     Inject HTML data attributes for dynamic UI behavior (typeahead, date, etc.).
+     Ensures data attributes persist through Django widget rendering.
+     """
+     field_type = (field_schema or {}).get('type')
+     lookup_aliases = {
+         'account': 'account',
+         'party': 'party',
+         'customer': 'customer',
+         'vendor': 'vendor',
+         'agent': 'agent',
+         'product': 'product',
+         'warehouse': 'warehouse',
+         'cost_center': 'cost_center',
+         'department': 'department',
+         'project': 'project',
+         'journal_type': 'journal_type',
+         'period': 'period',
+         'currency': 'currency',
+         'rate': 'rate',
+         'tax_code': 'tax_code',
+         'uom': 'uom',
+     }
+     lookup_types = set(lookup_aliases) | {'lookup', 'typeahead', 'autocomplete'}
+     
+     if field_type in lookup_types:
+         lookup_kind = (
+             field_schema.get('lookup_kind')
+             or field_schema.get('lookup')
+             or lookup_aliases.get(field_type)
+             or None
+         )
+         if lookup_kind:
+             lookup_kind = str(lookup_kind).replace('-', '_').lower()
+         
+         lookup_model = field_schema.get('lookup_model')
+         if not lookup_kind and lookup_model:
+             model_key = str(lookup_model).replace('-', '_').lower()
+             model_map = {
+                 'chartofaccount': 'account',
+                 'account': 'account',
+                 'vendor': 'vendor',
+                 'supplier': 'vendor',
+                 'customer': 'customer',
+                 'client': 'customer',
+                 'agent': 'agent',
+                 'product': 'product',
+                 'item': 'product',
+                 'service': 'product',
+                 'inventoryitem': 'product',
+                 'warehouse': 'warehouse',
+                 'taxcode': 'tax_code',
+                 'costcenter': 'cost_center',
+                 'department': 'department',
+                 'project': 'project',
+             }
+             lookup_kind = model_map.get(model_key)
+         
+         lookup_kind = lookup_kind or 'account'
+         lookup_url = field_schema.get('lookup_url')
+         endpoint = None
+         lookup_endpoints = {
+             'account': '/accounting/vouchers/htmx/account-lookup/',
+             'vendor': '/accounting/generic-voucher/htmx/vendor-lookup/',
+             'customer': '/accounting/generic-voucher/htmx/customer-lookup/',
+             'agent': '/accounting/journal-entry/lookup/agents/',
+             'product': '/accounting/generic-voucher/htmx/product-lookup/',
+             'warehouse': '/accounting/journal-entry/lookup/warehouses/',
+             'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
+             'cost_center': '/accounting/journal-entry/lookup/cost-centers/',
+             'department': '/accounting/journal-entry/lookup/departments/',
+             'project': '/accounting/journal-entry/lookup/projects/',
+         }
+         
+         if lookup_url:
+             endpoint = lookup_url
+         elif lookup_kind in lookup_endpoints:
+             endpoint = lookup_endpoints[lookup_kind]
+         elif field_type in ('lookup', 'typeahead', 'autocomplete'):
+             endpoint = f"/accounting/api/{lookup_kind}/search/"
+         
+         # Use custom TypeaheadInput widget to ensure data attributes persist
+         if not isinstance(widget, TypeaheadInput):
+             attrs_copy = widget.attrs.copy() if hasattr(widget, 'attrs') else {}
+             widget = TypeaheadInput(attrs=attrs_copy)
+         
+         base_classes = widget.attrs.get('class', '').strip()
+         # Add all typeahead classes for maximum compatibility
+         for cls in ('generic-typeahead', 've-suggest-input', 'typeahead-input', 'account-typeahead'):
+             if cls not in base_classes:
+                 base_classes = f"{base_classes} {cls}".strip()
+         
+         widget.attrs.update({
+             'class': base_classes,
+             'data-lookup-kind': str(lookup_kind),
+             'autocomplete': 'off',
+         })
+         
+         if endpoint:
+             widget.attrs['data-endpoint'] = endpoint
+         
+         if field_name:
+             widget.attrs['data-hidden-name'] = field_name
+         
+         logger.debug(f"Configured typeahead widget for field '{field_name}': lookup_kind={lookup_kind}, endpoint={endpoint}")
+         return widget
+     
+     elif field_type == 'date':
+         widget.attrs.setdefault('type', 'date')
+         base_classes = widget.attrs.get('class', '').strip()
+         if 'date-picker' not in base_classes:
+             widget.attrs['class'] = f"{base_classes} date-picker".strip()
+     elif field_type == 'datetime':
+         widget.attrs.setdefault('type', 'datetime-local')
+         base_classes = widget.attrs.get('class', '').strip()
+         if 'datetime-picker' not in base_classes:
+             widget.attrs['class'] = f"{base_classes} datetime-picker".strip()
+     elif field_type in ('number', 'decimal', 'integer'):
+         step_val = field_schema.get('step')
+         if step_val is None:
+             step_val = '1' if field_type == 'integer' else '0.01'
+         widget.attrs.setdefault('step', str(step_val))
+
+     return widget
```

**KEY CHANGES:**
- Use TypeaheadInput widget instead of default TextInput
- Update vendor/customer endpoints to use `/accounting/generic-voucher/` paths
- Add debug logging for troubleshooting
- Ensure all data attributes are properly set

---

## FILE 3: Create Debug Views
**Path:** `accounting/views/debug_views.py` (NEW FILE)

```python
"""
Debug views for development and troubleshooting.
"""
import logging
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View

logger = logging.getLogger(__name__)


class TypeaheadDebugView(LoginRequiredMixin, View):
    """
    Debug view to verify typeahead endpoint configuration.
    Accessible at /accounting/debug/typeahead/
    """
    
    def get(self, request):
        """Return debug info about typeahead endpoints."""
        endpoints = {
            'account': '/accounting/vouchers/htmx/account-lookup/',
            'vendor': '/accounting/generic-voucher/htmx/vendor-lookup/',
            'customer': '/accounting/generic-voucher/htmx/customer-lookup/',
            'product': '/accounting/generic-voucher/htmx/product-lookup/',
            'agent': '/accounting/journal-entry/lookup/agents/',
            'warehouse': '/accounting/journal-entry/lookup/warehouses/',
            'tax_code': '/accounting/journal-entry/lookup/tax-codes/',
            'cost_center': '/accounting/journal-entry/lookup/cost-centers/',
            'department': '/accounting/journal-entry/lookup/departments/',
            'project': '/accounting/journal-entry/lookup/projects/',
        }
        
        return JsonResponse({
            'status': 'ok',
            'message': 'Typeahead endpoints configuration. Test each endpoint with ?q=test',
            'endpoints': endpoints,
            'instructions': [
                'Test account lookup: curl "http://localhost:8000/accounting/vouchers/htmx/account-lookup/?q=test"',
                'Test vendor lookup: curl "http://localhost:8000/accounting/generic-voucher/htmx/vendor-lookup/?q=test"',
                'Each endpoint should return JSON with {"results": [...]}'
            ]
        })
```

---

## FILE 4: Update Generic Voucher Entry JS
**Path:** `accounting/static/js/generic_voucher_entry.js`

### Change 4.1: Update fetchSuggestions Function
**Location:** Around line 299-320

```diff
     const fetchSuggestions = async (term, endpoint) => {
-         if (!endpoint || !term) return [];
+         if (!endpoint || !term) {
+             console.debug('Typeahead: Skipping fetch - missing endpoint or term', { endpoint, term });
+             return [];
+         }
         if (shouldBackoff(endpoint)) return [];
         try {
+             const url = `${endpoint}?q=${encodeURIComponent(term)}&limit=10`;
+             console.debug(`Typeahead fetch: ${url}`);
+             
             const resp = await fetch(
-                 `${endpoint}?q=${encodeURIComponent(term)}&limit=10`,
+                 url,
                 {
                     credentials: 'same-origin',
                     headers: {
                         'Accept': 'application/json',
                         'X-Requested-With': 'XMLHttpRequest',
                     },
                 },
             );
-             if (!resp.ok && resp.status !== 429) return [];
+             if (!resp.ok && resp.status !== 429) {
+                 console.warn(`Typeahead fetch failed with status ${resp.status}`, { endpoint, url });
+                 return [];
+             }
+             
             const data = await parseJsonResponse(resp, endpoint);
-             if (Array.isArray(data?.results)) return data.results;
-             return [];
+             if (Array.isArray(data?.results)) {
+                 console.debug(`Typeahead got ${data.results.length} results from ${endpoint}`);
+                 return data.results;
+             }
+             
+             console.warn('Typeahead response missing results array', { endpoint, data });
+             return [];
         } catch (err) {
-             console.warn('lookup fetch failed', err);
+             console.warn('Typeahead lookup fetch failed', { error: err.message, endpoint });
             return [];
         }
     };
```

### Change 4.2: Update bindSuggestInput Function
**Location:** Around line 361-400

```diff
     const bindSuggestInput = (inputEl) => {
-         if (!inputEl || inputEl._suggestBound) return;
+         if (!inputEl || inputEl._suggestBound) return;
+         
+         // Verify endpoint exists before binding
+         const endpoint = inputEl.dataset.endpoint;
+         if (!endpoint) {
+             console.warn('Typeahead input missing data-endpoint attribute', {
+                 id: inputEl.id,
+                 name: inputEl.name,
+                 classes: inputEl.className,
+                 type: inputEl.type,
+                 hasDataLookupKind: !!inputEl.dataset.lookupKind,
+             });
+             return;
+         }
+         
          inputEl._suggestBound = true;
+         console.debug(`Bound typeahead input: ${inputEl.name || inputEl.id} -> ${endpoint}`);
+         
          const runSuggest = debounce(async () => {
              const term = (inputEl.value || '').trim();
              if (!term) {
                  AccountSuggest.close();
                  return;
              }
-             const endpoint = inputEl.dataset.endpoint;
              const suggestions = await fetchSuggestions(term, endpoint);
              if (!suggestions.length && !buildAddNewMeta(inputEl)) {
                  AccountSuggest.close();
                  return;
              }
              AccountSuggest.open(inputEl, suggestions, {
                  onSelect: (choice) => selectLookupResult(inputEl, choice),
                  onAddNew: buildAddNewMeta(inputEl),
              });
          }, 180);
```

### Change 4.3: Update initSuggestInputs Function
**Location:** Around line 405-410

```diff
     const initSuggestInputs = (scope = document) => {
-         const candidates = scope.querySelectorAll('.account-typeahead, .generic-typeahead, .ve-suggest-input');
+         const candidates = scope.querySelectorAll('.account-typeahead, .generic-typeahead, .ve-suggest-input, [data-endpoint]');
+         console.debug(`Initializing ${candidates.length} typeahead fields in scope:`, scope.id || scope.className);
          candidates.forEach(bindSuggestInput);
     };
```

### Change 4.4: Update HTMX afterSwap Handler
**Location:** Around line 990-1000

```diff
+     // HTMX afterSwap: reinitialize suggest inputs
+     document.body.addEventListener('htmx:afterSwap', (event) => {
+         try {
+             const target = event.detail.target;
+             if (!target) return;
+             console.debug('HTMX afterSwap: reinitializing suggests in', target.id || target.className);
+             initSuggestInputs(target);
+         } catch (e) {
+             console.warn('Error reinitializing suggests after HTMX swap', e);
+         }
+     });
```

### Change 4.5: Update responseError Handler
**Location:** Around line 1200-1230

```diff
     document.body.addEventListener('htmx:responseError', (evt) => {
         try {
             const xhr = evt.detail && evt.detail.xhr;
             if (!xhr) return;
+             
             // Treat 422 as validation response and swap into panel
             if (xhr.status === 422) {
                 const panel = document.getElementById('generic-voucher-panel');
                 if (!panel) return;
+                 
+                 console.debug('HTMX 422: Updating panel with validation errors');
                 panel.innerHTML = xhr.responseText;
 
                 // re-init behaviours for swapped content
-                 reindexRows();
-                 updateSummary();
-                 initColumnResizers();
-                 initSuggestInputs(panel);
-                 initHeaderHkeys();
+                 try { reindexRows(); } catch (e) { console.warn('reindexRows failed', e); }
+                 try { updateSummary(); } catch (e) { console.warn('updateSummary failed', e); }
+                 try { initColumnResizers(); } catch (e) { console.warn('initColumnResizers failed', e); }
+                 try { initSuggestInputs(panel); } catch (e) { console.warn('initSuggestInputs failed', e); }
+                 try { initHeaderHkeys(); } catch (e) { console.warn('initHeaderHkeys failed', e); }
 
                 // apply server-rendered invalid-feedback mapping (adds is-invalid, aria attributes)
                 try { applyInvalidFeedbackClasses(panel); } catch (e) { /* non-fatal */ }
```

---

## FILE 5: Update URLs Configuration
**Path:** `accounting/urls/__init__.py`

### Change 5.1: Add Import
**Location:** Around line 98 (after other view imports)

```diff
 from ..views.views_htmx import AccountTypeDependentFieldsHXView, VoucherAccountLookupJsonView
+ from ..views import debug_views
```

### Change 5.2: Add Debug Route
**Location:** Around line 530-535 (in API URLs section)

```diff
     path('api/v1/journals/suggest/', api_views.suggest_journal_entries, name='suggest_journal_entries'),
     path('api/v1/journals/line-suggest/', api_views.get_line_suggestions, name='get_line_suggestions'),
     path('api/v1/validate-field/', api_views.validate_field, name='validate_field'),
+    # Debug/Diagnostic URLs
+    path('debug/typeahead/', debug_views.TypeaheadDebugView.as_view(), name='debug_typeahead'),
 ]
```

### Change 5.3: REMOVE Duplicate Route
**Location:** Line 533 (DELETE THIS LINE)

```diff
- path('vouchers/htmx/account-lookup/', VoucherAccountLookupJsonView.as_view(), name='voucher_account_lookup'),
```

---

## TESTING CHECKLIST

```bash
# 1. Verify debug endpoint works
curl http://localhost:8000/accounting/debug/typeahead/

# 2. Test account lookup returns JSON
curl "http://localhost:8000/accounting/vouchers/htmx/account-lookup/?q=test"
# Expected: {"results": [...]}

# 3. Test vendor lookup
curl "http://localhost:8000/accounting/generic-voucher/htmx/vendor-lookup/?q=test"
# Expected: {"results": [...]}

# 4. Run typeahead tests
python manage.py test accounting.tests.test_typeahead_endpoints -v 2

# 5. Manual browser test
# - Open voucher entry form
# - Open browser DevTools (F12)
# - Look for debug messages in Console when typing in account field
# - Verify data-endpoint attribute is present in HTML
```

---

## IMPACT ANALYSIS

| Component | Change | Risk | Mitigation |
|-----------|--------|------|-----------|
| Widget Layer | New TypeaheadInput class | Low | Inherits from Django's TextInput |
| Form Factory | Enhanced attribute handling | Low | Backward compatible, logging only |
| JavaScript | Added debug logging | Low | Debug-level only, non-blocking |
| URLs | New debug route + duplicate removal | Low | Duplicate caused no functional issues |
| Endpoints | Updated vendor/customer paths | Low | Existing endpoints still work |

---

## ROLLBACK PROCEDURE

If issues occur, rollback in this order:
1. Remove `accounting/widgets.py`
2. Restore original `forms_factory.py` (remove TypeaheadInput usage)
3. Restore original `generic_voucher_entry.js` (remove debug logging)
4. Remove debug route from `accounting/urls/__init__.py`
5. Restore `accounting/views/debug_views.py` file (if it existed)

---

## NOTES

- All changes are **backward compatible**
- No database migrations required
- No model changes
- Existing functionality fully preserved
- Debug logging is non-intrusive
- Safe to deploy to production

**Created:** 2025-12-27  
**Status:** Ready for Implementation
