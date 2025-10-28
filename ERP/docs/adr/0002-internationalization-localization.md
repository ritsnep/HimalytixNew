# ADR-0002: Internationalization and Localization Strategy

**Status:** Accepted  
**Date:** 2024-Q4  
**Decision Makers:** Product Team, Engineering Lead  
**Technical Story:** Phase 3 Task 6 - i18n/l10n Implementation

---

## Context and Problem Statement

The Nepal market requires support for both English and Nepali languages, with Nepali using the Devanagari script (RTL support not required for Devanagari, but considered for potential Arabic/Urdu users). How should we implement internationalization (i18n) and localization (l10n) to support multiple languages, currencies (NPR), date formats (Bikram Sambat calendar), and number formats?

## Decision Drivers

* **Language Support**: English (default), Nepali (primary market)
* **Currency**: Nepali Rupee (NPR) with proper formatting
* **Date Formats**: Gregorian + Bikram Sambat calendar support
* **Number Formats**: Nepali conventions (lakh/crore vs. million/billion)
* **RTL Support**: Optional for future expansion (Arabic, Urdu)
* **Developer Experience**: Easy to add new translations
* **Performance**: Minimal runtime overhead

## Considered Options

1. **Django Built-in i18n** (gettext + .po files)
2. **Third-party Service** (Transifex, Lokalise)
3. **Database-driven Translations** (django-modeltranslation)

## Decision Outcome

**Chosen option:** "Django Built-in i18n (gettext)", because:
- Native Django support, well-documented
- Offline translations (no external service dependency)
- Version-controlled .po files (Git-friendly)
- Supports pluralization, context, lazy translation
- Zero runtime cost (compiled .mo files)

### Implementation Details

- **Translation Files**: `i18n/locale/ne/LC_MESSAGES/django.po`
- **Middleware**: `django.middleware.locale.LocaleMiddleware`
- **Template Tags**: `{% load i18n %}`, `{% trans %}`, `{% blocktrans %}`
- **JavaScript**: `django.views.i18n.JavaScriptCatalog` for HTMX/Alpine.js
- **Formats**: Custom `formats.py` for NPR currency, Nepali number conventions
- **Language Switcher**: Cookie-based persistence (`django_language`)

### Positive Consequences

* Full control over translations (no vendor lock-in)
* Fast (compiled .mo files loaded at startup)
* Translators can use standard tools (Poedit, Lokalize)
* Git-friendly (line-by-line diffs in .po files)
* Supports both Python and JavaScript code

### Negative Consequences

* Manual .po file management (vs. cloud-based services)
* Requires `compilemessages` step in deployment
* Non-technical translators need training on .po format
* No built-in translation memory/glossary

## Pros and Cons of the Options

### Django Built-in i18n (gettext)

* **Good**, zero external dependencies
* **Good**, mature ecosystem (Poedit, i18n tools)
* **Good**, version-controlled translations
* **Good**, fast runtime performance
* **Neutral**, requires manual .po editing
* **Bad**, no collaborative translation platform

### Third-party Service (Transifex, Lokalise)

* **Good**, web-based translation UI
* **Good**, collaboration features (translation memory, glossaries)
* **Good**, translators don't need developer tools
* **Bad**, external dependency (availability, cost)
* **Bad**, vendor lock-in
* **Bad**, requires API integration

### Database-driven Translations (django-modeltranslation)

* **Good**, admin UI for translations
* **Good**, real-time updates without deployment
* **Bad**, performance overhead (additional queries)
* **Bad**, database bloat (N columns per translated field)
* **Bad**, complicates migrations

## Links

* Implemented in: `i18n/locale/`, `utils/i18n.py`
* Completion: [PHASE_3_I18N_COMPLETION.md](../../PHASE_3_I18N_COMPLETION.md)
* Django i18n docs: https://docs.djangoproject.com/en/stable/topics/i18n/

---

## Compliance and Review

* **Reviewed by:** Product Manager, Engineering Lead
* **Review date:** 2024-Q4
* **Next review:** 2025-Q2 (when adding new languages)
