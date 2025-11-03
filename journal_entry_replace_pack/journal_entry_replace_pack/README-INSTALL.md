# Journal Entry Replacement Pack (Django + HTMX)

This pack replaces your existing Journal Entry page with the Excel-like grid UI you provided.
It includes:
- Template: `templates/accounting/journal_entry.html`
- JS: `static/accounting/js/voucher_entry.js` (modified for Django endpoints + CSRF)
- CSS: `static/accounting/css/voucher_entry.css`
- Views: `accounting/views/journal_entry.py`
- URLs: `accounting/urls.py`
- Sidebar snippet: `sidebar_snippet.html`

## What to replace (summary)
1) **Template**
   Replace your existing Journal Entry template with `templates/accounting/journal_entry.html`.
   If your base template isn't `base.html` or your block names differ,
   adjust the `{% extends %}` and blocks accordingly.

2) **Static files**
   Replace your old Journal JS/CSS (if any) with:
     - `static/accounting/js/voucher_entry.js`
     - `static/accounting/css/voucher_entry.css`
   Then update the template's `{% static %}` paths if you change locations.

3) **Views + URLs**
   If your app is named differently, move `accounting/views/journal_entry.py` into your app
   and include the URL patterns in your app's `urls.py` (or copy the entries).
   Add to project-level urls:
     ```python
     # config/urls.py
     from django.urls import path, include
     urlpatterns = [
         # ... other routes ...
         path("", include("accounting.urls")),  # or your app's urls
     ]
     ```

4) **Sidebar**
   Use `sidebar_snippet.html` to replace your Journal Entry link:
     ```django
     <li class="nav-item">
       <a class="nav-link" href="{% url 'accounting:journal_entry' %}">
         <i class="fas fa-book-open"></i> Journal Entry
       </a>
     </li>
     ```

5) **CSRF & Endpoints**
   The script reads endpoints from data-attributes on `#app`:
     - `data-endpoint-save="{% url 'accounting:journal_save_draft' %}"`
     - `data-endpoint-submit="{% url 'accounting:journal_submit' %}"`
     - `data-endpoint-approve="{% url 'accounting:journal_approve' %}"`
   The JS will try to POST JSON to these endpoints. If not reachable, it will fallback
   to local-only behavior (console log + alert). We included `@csrf_exempt` for demo;
   remove it and rely on the cookie-based CSRF token we already send via `X-CSRFToken`.

6) **HTMX**
   HTMX is loaded in the template but not required for core features. Use it later for
   search/lookup popovers, async validations, etc.

7) **Tailwind & SheetJS**
   We include CDN versions in the template. If your base already loads Tailwind, you can
   remove the line. SheetJS (xlsx) is needed for import/export.

8) **Collect static**
   Run:
     ```bash
     python manage.py collectstatic
     ```
   Ensure `STATIC_URL` and `STATICFILES_DIRS` or `STATIC_ROOT` are correctly configured.

## Notes on the modified JS
- We inserted a **Django Integration Header** at the top for CSRF + endpoints.
- We replaced the handlers for **Save Draft**, **Submit**, and **Approve** to call the backend
  if endpoints exist; otherwise, they gracefully fallback to local behavior.
- Everything else from your original UI remains the same (Excel paste, column manager,
  UDFs, totals, CSV/XLSX import/export, etc.).

## File Map
- templates/accounting/journal_entry.html
- static/accounting/css/voucher_entry.css
- static/accounting/js/voucher_entry.js
- accounting/views/journal_entry.py
- accounting/urls.py
- sidebar_snippet.html

## Done.
Drop these in, wire URLs, and it will replace your Journal Entry page.
