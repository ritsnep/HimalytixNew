# Configurable Reporting System – Use Case Guide

## Purpose
Enable flexible reporting with safe fallbacks: base (pre-built) reports work out-of-the-box, while custom layouts can be enabled globally and per report for org-specific designs.

## Core Concepts
- **Base vs Custom**: Base templates are always available. Custom templates render only when `ENABLE_CUSTOM_REPORTS` is true *and* the report’s `is_custom_enabled` flag is on.
- **Per-Report Scope**: Each `ReportDefinition` can be global or organization-scoped, with optional gallery templates (`ReportTemplate`).
- **Data/Render Separation**: `ReportDataService` builds contexts; `ReportRenderer` picks custom or base template and handles exports (HTML/PDF/Excel/CSV).
- **Scheduling**: `ScheduledReport` + Celery beat task `reporting.tasks.dispatch_due_reports` email exports on a cadence.

## User Journeys
1) **View a Report**
   - Go to `/reports/<code>/`.
   - If custom allowed and a template exists, render it; otherwise use base template.
   - Export buttons: PDF, Excel, CSV, HTML.

2) **Design a Custom Template (staff)**
   - Open `/reports/<code>/designer/`.
   - Drag/drop layout (GrapesJS), load gallery templates, fetch sample data, and save.
   - Saved HTML is stored on `ReportDefinition` and as a versioned `ReportTemplate`.

3) **Manage Templates via API (staff)**
   - GET `/reports/api/templates/?code=...&include_gallery=1` to fetch active template + gallery list.
   - POST `/reports/api/templates/` with `template_html`, `engine`, `is_custom_enabled` to save new version.

4) **Schedule Delivery (staff)**
   - List/manage: `/reports/schedules/` (toggle active, run now).
   - Celery beat entry: `reporting.tasks.dispatch_due_reports` (interval via `REPORTING_SCHEDULE_INTERVAL_SECONDS`, default 300s).

## Report Seeds (Base + Gallery)
- `journal_report` (pilot)
- `general_ledger`
- `trial_balance`
- `profit_loss`
- `balance_sheet`

Each has a base template under `reporting/templates/reporting/base/` and a “Modern” gallery template under `reporting/templates/reporting/gallery/`.

## Configuration
- Env: `ENABLE_CUSTOM_REPORTS` (default on), `REPORTING_SCHEDULE_INTERVAL_SECONDS` (default 300).
- INSTALLED_APPS includes `reporting`; URLs mounted at `/reports/`.
- Exports rely on: `weasyprint` (PDF), `openpyxl` (Excel).

## Permissions & Safety
- Designer/API restricted to staff.
- Templates are sanitized server-side (script/JS protocol stripped).
- Org scoping enforced when resolving definitions/templates.

## Quick Start
1. Install deps: `pip install weasyprint openpyxl`.
2. Migrate: `python manage.py migrate reporting`. 
3. Run Celery worker + beat so scheduled runs dispatch.
4. Visit `/reports/` to open reports or `/reports/<code>/designer/` to customize.
