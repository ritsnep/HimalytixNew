# Dual AD/BS Calendar Datepicker – Implementation Reference

This document summarizes the dual-calendar (Gregorian AD / Bikram Sambat BS) implementation and how to use, configure, and test it.

## What was added
- **Conversion utilities:** `utils/calendars.py` centralizes AD↔BS conversion (`bs_to_ad*`, `ad_to_bs*`, `maybe_coerce_bs_date`, `CalendarMode`).
- **Org-level setting:** `CompanyConfig.calendar_mode` (AD | BS | DUAL) with migration `0024_companyconfig_calendar_mode.py`; exposed via context (`calendar_mode`) and request (`request.calendar_mode`).
- **Frontend assets:** Nepali datepicker v5 bundled in `static/libs/nepali-datepicker/…` and helper JS `static/js/dual-calendar.js` (HTMX-safe init).
- **Reusable widget:** `DualCalendarWidget` (`utils/widgets.py`) + template `templates/widgets/dual_calendar_widget.html`; server-side fallback converts BS to AD on submit.
- **Template helpers:** `templatetags/calendar_extras.py` (`to_bs`, `dual_date`).
- **Usage example:** Ledger filter dates use the dual picker; accounting `JournalForm` now renders with `DualCalendarWidget`.
- **Global form wiring:** `BootstrapFormMixin` (accounting/billing/inventory/service/enterprise) now swaps every `forms.DateField` to the dual picker; purchasing (`OrganizationBoundFormMixin`), LPG (`OrganizationModelForm`), and dynamic UDFs (`DynamicFormMixin`) do the same so all business date inputs render with BS/AD support without per-form tweaks.
- **Date seeding config:** `CompanyConfig.calendar_date_seed` (Today or Last-or-today) controls initial date prefills; backend defaults use the last org record when available, otherwise today.

## How to configure
1. **Install deps:** `pip install -r requirements.txt` (adds `nepali-datetime`).
2. **Migrate setting:** `python manage.py migrate usermanagement 0024` (or full migrate) to add `calendar_mode`.
3. **Set default mode per org:** Update `CompanyConfig.calendar_mode` to `AD`, `BS`, or `DUAL`. The template context exposes `calendar_mode` automatically.

## How to use the widget in forms
```python
from utils.widgets import DualCalendarWidget
from utils.calendars import CalendarMode

class MyForm(forms.Form):
    date = forms.DateField(
        widget=DualCalendarWidget(default_view=CalendarMode.DUAL)
    )
```
- The AD input keeps the submitted name; BS input is linked for conversion.
- Toggle button appears only in `DUAL` mode; `BS` or `AD` modes hide the alternate view.
- For templates not using Django forms, mimic the markup used in `inventory/ledger_report.html`.

## Frontend behavior
- `dual-calendar.js` wires two-way sync using `NepaliFunctions.AD2BS/BS2AD`.
- Works with HTMX: listeners mount on `DOMContentLoaded` and `htmx:afterSwap`.
- Global defaults injected in `partials/base.html` (`window.CALENDAR_MODE`, `CALENDAR_INITIAL_VIEW`).

## Server-side safety
- If the browser sends the BS field (e.g., JS disabled), `DualCalendarWidget.value_from_datadict` converts BS→AD before validation.
- `maybe_coerce_bs_date` tolerates Nepali numerals and slash separators.

## Testing guidance
- Targeted conversion/widget tests live in `tests/test_calendars.py`.
- Example command (single-thread, no coverage):  
  ```bash
  cd ERP
  pytest tests/test_calendars.py --no-cov -n0 --maxfail=1
  ```
  If using a shared PostgreSQL test DB, ensure it is clean (drop `test_erpdb` or run without `--reuse-db`) to avoid duplicate sequence errors.
- Manual smoke:
  1. Set an org `calendar_mode` to `DUAL`.
  2. Open a journal form and toggle BS/AD—both inputs stay in sync.
  3. On ledger report filters, enter a BS date; verify AD value updates and the filter applies.

## Integration notes
- Ensure `{{ form.media }}` or base assets include `nepali.datepicker` CSS/JS (already injected via base).
- For reports, use `{{ some_date|to_bs }}` or `{% dual_date some_date calendar_mode %}` when BS display is needed.
