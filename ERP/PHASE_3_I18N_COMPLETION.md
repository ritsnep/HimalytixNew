<<<<<<< ours
# Phase 3 — Internationalization (i18n) + Language/Region Switching

This document summarizes the i18n work completed so far and provides clear guidance to extend it across the project. It’s designed as a quick handoff for continued implementation.

## Goals
- Provide project-wide JSON-based translations for UI text.
- Add end-to-end language and region switching.
- Replace hardcoded UI strings in key templates/components.
- Internationalize user-facing server responses (HTMX voucher handlers).
- Provide a validator to track missing/unused i18n keys.

## What’s Implemented

### 1) Global i18n loading and context
- utils/i18n.py
  - Merges translations from `i18n/<lang>.json` and `accounting/i18n/<lang>.json` with fallback to English.
  - Exposes `i18n`, `current_language`, `current_region` to every template via the context processor `i18n_context`.
  - Helpers:
    - `load_translations(lang_code)`
    - `get_current_language(request)`
    - `i18n_context(request)`

- dashboard/settings.py
  - Adds `django.middleware.locale.LocaleMiddleware`.
  - Registers the context processor: `utils.i18n.i18n_context`.
  - Defines `LANGUAGES = [('en', 'English'), ('ne', 'Nepali')]` and `LANGUAGE_COOKIE_NAME`.

### 2) Language + Region switching
- dashboard/views.py
  - `set_language` endpoint: persists selection in session/cookie, activates language.
  - `set_region` endpoint: persists region preference (e.g., `US`, `GB`, `IN`, `EU`).

- dashboard/urls.py
  - Adds routes: `/i18n/set-language/`, `/i18n/set-region/`.

- templates/partials/header.html
  - Adds Language menu with English + Nepali items.
  - Adds Region menu with common regions.

### 3) Base template JS exposure
- templates/partials/base.html
  - Injects `window.I18N` (translations), `window.CURRENT_LANGUAGE`, `window.CURRENT_REGION`, and a simple `t(key, fallback)` helper for client-side usage.
  - Sets `<html lang="{{ current_language }}>`.

### 4) Template helper for dotted keys
- templatetags/i18n_extras.py
  - `i18n_get` filter to fetch dotted keys: `{{ i18n|i18n_get:'journal.entry.title' }}`.

### 5) Completed translations (English + Nepali)
- i18n/en.json — filled with keys for Journal/Voucher UI (buttons, actions, labels, columns, attachments, totals, validation, shortcuts, server messages for HTMX handlers).
- i18n/ne.json — added Nepali equivalents for the same keys.

### 6) Replace hardcoded UI strings (initial pass)
- accounting/templates/accounting/base_voucher.html
  - Title, section headers, buttons, common labels use i18n keys.

- accounting/templates/accounting/partials/totals_section.html
  - Totals and balance labels use i18n keys.

- accounting/templates/accounting/journal_entry.html
  - Save button, dropdown actions (Print/Export/Download Sample/Duplicate/Save as Recurring), Details label, AI Assist placeholder use i18n keys.

### 7) Server-side messages i18n (HTMX voucher handlers)
- accounting/views/voucher_htmx_handlers.py
  - Imports i18n helpers and defines a small `_t(request, key, fallback, **kwargs)` formatter.
  - All user-facing messages (errors, forbidden/action messages, balanced/unbalanced, deletion success) use i18n keys with interpolation.

### 8) i18n coverage validator
- scripts/validate_i18n.py
  - Scans templates/JS for `i18n[...]`, `i18n.key`, `i18n|i18n_get:'...'` and JS `t('...')` usages.
  - Compares against en.json; prints missing/unused keys.

## Usage Examples

### In templates
- Underscore key: `{{ i18n.journal_entry_title|default:"Journal Entry" }}`
- Dotted key: `{{ i18n|i18n_get:'journal.entry.title'|default:"Journal Entry" }}`
- Bracket access: `{{ i18n["actions.print"]|default:"Print" }}`

### In Python (server responses)
```
msg = self._t(request, 'voucher.error.forbidden.post', 'Cannot post a {status} journal', status=journal.status)
```

### In JavaScript
```
toastr.success(t('actions.export', 'Export started'));
```

## Adding a New Language
1) Add `<lang>.json` in `i18n/` (and optionally in `accounting/i18n/` for app-specific overrides).
2) Mirror the keys from `i18n/en.json`.
3) Add `('<lang>', '<Display Name>')` in `dashboard/settings.py` → `LANGUAGES`.
4) Add a menu item in `templates/partials/header.html` calling `/i18n/set-language/?lang=<lang>`.

## Key Style and Structure
- Prefer namespaced dotted keys for grouping (e.g., `voucher.button.save_draft`, `totals.total_debit`).
- Maintain temporary underscore aliases where currently used; migrate gradually.
- Use `{placeholder}` in values for formatted strings; provide `**kwargs` when calling `_t()`.

## Common Pitfalls + Solutions
- Mixed key styles: Keep underscore aliases for backward compatibility; use `i18n_get` to adopt dotted keys.
- Multiple source files: The loader merges `i18n/` first, then `accounting/i18n/` so app keys override project keys; English fills gaps.
- Encoding artifacts: Some historical templates had odd characters; replaced with standard text and i18n keys.
- JS literals: Expose `window.I18N` + `t()` and refactor progressively.

## What Remains (High-Value Next Steps)
1) Complete template migration
   - Approval UI: `accounting/templates/accounting/approval/approval_dashboard.html`, `approval_queue.html`, `approval_history.html`.
   - Shared partials: `attachments_section.html`, `audit_trail_display.html`, `action_buttons.html`, `line_items_table.html`, `totals_display.html`, `validation_errors.html`.
   - Replace hardcoded text with i18n keys; add any new keys to `i18n/en.json` (and `i18n/ne.json`).

2) Client-side i18n
   - Refactor `accounting/static/js/*.js` (voucher_htmx.js, voucher_forms.js, voucher_validation.js, voucher_totals.js) to use `t('...')` for alerts/toasts.

3) Regional formatting
   - Use `current_region` to format dates, numbers, and currencies on server (Django localization) and client (Intl API) where applicable.

4) Run validator and reconcile
   - `python scripts/validate_i18n.py` — add or remove keys per report.

## Quick Checklist
- [x] Global JSON i18n loader + context processor
- [x] Language/Region switch endpoints
- [x] Header UI for language/region
- [x] JS exposure (`window.I18N`, `t()`)
- [x] Template helper (`i18n_get`)
- [x] English i18n coverage for current UI
- [x] Nepali added as a second language
- [x] Key templates updated (voucher base, journal, totals section)
- [x] HTMX voucher handlers i18n-ized
- [x] i18n validator script

## File Index (for review)
- i18n/en.json
- i18n/ne.json
- utils/i18n.py
- templatetags/i18n_extras.py
- dashboard/settings.py
- dashboard/urls.py
- dashboard/views.py
- templates/partials/base.html
- templates/partials/header.html
- accounting/templates/accounting/base_voucher.html
- accounting/templates/accounting/journal_entry.html
- accounting/templates/accounting/partials/totals_section.html
- accounting/views/voucher_htmx_handlers.py
- scripts/validate_i18n.py

## How to Continue
1) Pick a template or JS file with visible text.
2) Replace literals with `i18n[...]` (or `i18n_get`) and add the corresponding key/value in `en.json` (and `ne.json`).
3) Use `_t(request, key, fallback, **kwargs)` for server responses.
4) Run the validator and reconcile.
5) Repeat until pages/components are fully covered.

=======
# Phase 3 — Internationalization (i18n) + Language/Region Switching

This document summarizes the i18n work completed so far and provides clear guidance to extend it across the project. It’s designed as a quick handoff for continued implementation.

## Goals
- Provide project-wide JSON-based translations for UI text.
- Add end-to-end language and region switching.
- Replace hardcoded UI strings in key templates/components.
- Internationalize user-facing server responses (HTMX voucher handlers).
- Provide a validator to track missing/unused i18n keys.

## What’s Implemented

### 1) Global i18n loading and context
- utils/i18n.py
  - Merges translations from `i18n/<lang>.json` and `accounting/i18n/<lang>.json` with fallback to English.
  - Exposes `i18n`, `current_language`, `current_region` to every template via the context processor `i18n_context`.
  - Helpers:
    - `load_translations(lang_code)`
    - `get_current_language(request)`
    - `i18n_context(request)`

- dashboard/settings.py
  - Adds `django.middleware.locale.LocaleMiddleware`.
  - Registers the context processor: `utils.i18n.i18n_context`.
  - Defines `LANGUAGES = [('en', 'English'), ('ne', 'Nepali')]` and `LANGUAGE_COOKIE_NAME`.

### 2) Language + Region switching
- dashboard/views.py
  - `set_language` endpoint: persists selection in session/cookie, activates language.
  - `set_region` endpoint: persists region preference (e.g., `US`, `GB`, `IN`, `EU`).

- dashboard/urls.py
  - Adds routes: `/i18n/set-language/`, `/i18n/set-region/`.

- templates/partials/header.html
  - Adds Language menu with English + Nepali items.
  - Adds Region menu with common regions.

### 3) Base template JS exposure
- templates/partials/base.html
  - Injects `window.I18N` (translations), `window.CURRENT_LANGUAGE`, `window.CURRENT_REGION`, and a simple `t(key, fallback)` helper for client-side usage.
  - Sets `<html lang="{{ current_language }}>`.

### 4) Template helper for dotted keys
- templatetags/i18n_extras.py
  - `i18n_get` filter to fetch dotted keys: `{{ i18n|i18n_get:'journal.entry.title' }}`.

### 5) Completed translations (English + Nepali)
- i18n/en.json — filled with keys for Journal/Voucher UI (buttons, actions, labels, columns, attachments, totals, validation, shortcuts, server messages for HTMX handlers).
- i18n/ne.json — added Nepali equivalents for the same keys.

### 6) Replace hardcoded UI strings (initial pass)
- accounting/templates/accounting/base_voucher.html
  - Title, section headers, buttons, common labels use i18n keys.

- accounting/templates/accounting/partials/totals_section.html
  - Totals and balance labels use i18n keys.

- accounting/templates/accounting/journal_entry.html
  - Save button, dropdown actions (Print/Export/Download Sample/Duplicate/Save as Recurring), Details label, AI Assist placeholder use i18n keys.

### 7) Server-side messages i18n (HTMX voucher handlers)
- accounting/views/voucher_htmx_handlers.py
  - Imports i18n helpers and defines a small `_t(request, key, fallback, **kwargs)` formatter.
  - All user-facing messages (errors, forbidden/action messages, balanced/unbalanced, deletion success) use i18n keys with interpolation.

### 8) i18n coverage validator
- scripts/validate_i18n.py
  - Scans templates/JS for `i18n[...]`, `i18n.key`, `i18n|i18n_get:'...'` and JS `t('...')` usages.
  - Compares against en.json; prints missing/unused keys.

## Usage Examples

### In templates
- Underscore key: `{{ i18n.journal_entry_title|default:"Journal Entry" }}`
- Dotted key: `{{ i18n|i18n_get:'journal.entry.title'|default:"Journal Entry" }}`
- Bracket access: `{{ i18n["actions.print"]|default:"Print" }}`

### In Python (server responses)
```
msg = self._t(request, 'voucher.error.forbidden.post', 'Cannot post a {status} journal', status=journal.status)
```

### In JavaScript
```
toastr.success(t('actions.export', 'Export started'));
```

## Adding a New Language
1) Add `<lang>.json` in `i18n/` (and optionally in `accounting/i18n/` for app-specific overrides).
2) Mirror the keys from `i18n/en.json`.
3) Add `('<lang>', '<Display Name>')` in `dashboard/settings.py` → `LANGUAGES`.
4) Add a menu item in `templates/partials/header.html` calling `/i18n/set-language/?lang=<lang>`.

## Key Style and Structure
- Prefer namespaced dotted keys for grouping (e.g., `voucher.button.save_draft`, `totals.total_debit`).
- Maintain temporary underscore aliases where currently used; migrate gradually.
- Use `{placeholder}` in values for formatted strings; provide `**kwargs` when calling `_t()`.

## Common Pitfalls + Solutions
- Mixed key styles: Keep underscore aliases for backward compatibility; use `i18n_get` to adopt dotted keys.
- Multiple source files: The loader merges `i18n/` first, then `accounting/i18n/` so app keys override project keys; English fills gaps.
- Encoding artifacts: Some historical templates had odd characters; replaced with standard text and i18n keys.
- JS literals: Expose `window.I18N` + `t()` and refactor progressively.

## What Remains (High-Value Next Steps)
1) Complete template migration
   - Approval UI: `accounting/templates/accounting/approval/approval_dashboard.html`, `approval_queue.html`, `approval_history.html`.
   - Shared partials: `attachments_section.html`, `audit_trail_display.html`, `action_buttons.html`, `line_items_table.html`, `totals_display.html`, `validation_errors.html`.
   - Replace hardcoded text with i18n keys; add any new keys to `i18n/en.json` (and `i18n/ne.json`).

2) Client-side i18n
   - Refactor `accounting/static/js/*.js` (voucher_htmx.js, voucher_forms.js, voucher_validation.js, voucher_totals.js) to use `t('...')` for alerts/toasts.

3) Regional formatting
   - Use `current_region` to format dates, numbers, and currencies on server (Django localization) and client (Intl API) where applicable.

4) Run validator and reconcile
   - `python scripts/validate_i18n.py` — add or remove keys per report.

## Quick Checklist
- [x] Global JSON i18n loader + context processor
- [x] Language/Region switch endpoints
- [x] Header UI for language/region
- [x] JS exposure (`window.I18N`, `t()`)
- [x] Template helper (`i18n_get`)
- [x] English i18n coverage for current UI
- [x] Nepali added as a second language
- [x] Key templates updated (voucher base, journal, totals section)
- [x] HTMX voucher handlers i18n-ized
- [x] i18n validator script

## File Index (for review)
- i18n/en.json
- i18n/ne.json
- utils/i18n.py
- templatetags/i18n_extras.py
- dashboard/settings.py
- dashboard/urls.py
- dashboard/views.py
- templates/partials/base.html
- templates/partials/header.html
- accounting/templates/accounting/base_voucher.html
- accounting/templates/accounting/journal_entry.html
- accounting/templates/accounting/partials/totals_section.html
- accounting/views/voucher_htmx_handlers.py
- scripts/validate_i18n.py

## How to Continue
1) Pick a template or JS file with visible text.
2) Replace literals with `i18n[...]` (or `i18n_get`) and add the corresponding key/value in `en.json` (and `ne.json`).
3) Use `_t(request, key, fallback, **kwargs)` for server responses.
4) Run the validator and reconcile.
5) Repeat until pages/components are fully covered.

>>>>>>> theirs
