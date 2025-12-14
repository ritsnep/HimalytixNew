# Backup & Export Plan

## Goals
- Give org admins a self-service way to export key entities (products, contacts/customers, invoices/transactions) as CSV/XLSX from the UI.
- Provide a one-click "Backup My Data" that packages all tenant data (schema-based) into an encrypted archive.
- Run automated nightly backups with retention, optional cloud upload, and minimal load on the primary DB.
- Keep restores controlled and auditable; prioritize data availability and security.

## Multi-tenant constraints
- Tenancy is schema-based (`tenancy.middleware.ActiveTenantMiddleware` sets `search_path` to `tenant.data_schema`). All backup/export commands must pin the schema explicitly; do not rely solely on request middleware when running out-of-band tasks.
- Enumerate tenants via `Tenant` and respect `is_active`. Per-tenant storage paths should include the `tenant.code` to avoid collisions.

## Quick win: manual exports (CSV/XLSX)
- Scope (minimum): `inventory.Product`, `accounting.Customer` (or CRM equivalent), `accounting.SalesInvoice` with `SalesInvoiceLine` (flatten lines or deliver two sheets), and `purchasing` items if needed.
- Patterns to reuse: existing CSV writers in `accounting.views.analytics_views`, `accounting.views.import_export_views`, and `reporting.services` for streaming responses.
- Endpoint sketch: `GET /export/<dataset>.<format>` guarded by org-admin permission (`PermissionUtils.has_codename`); `format in {csv, xlsx}`. Dataset map drives queryset and column list.
- Implementation approach:
  - Service layer `export_service.export_dataset(dataset: str, qs: QuerySet, fmt: str) -> (bytes/stream, filename, content_type)` using `csv` and `openpyxl` or `tablib` (already bundled by django-import-export if available).
  - Stream responses (`HttpResponse` with `Content-Disposition`) for small exports; for large sets, enqueue a Celery task and email/download when ready.
- UI: Add an "Exports" tab/button in admin/dashboard with per-dataset buttons and format picker. Show status if async.

## One-click "Backup My Data" (on-demand)
- Entry point: POST from org-admin UI → triggers Celery task `backups.tasks.run_tenant_backup(tenant_id, requested_by)`.
- Validation: Rate limiting (e.g., max 1 manual backup per hour) to prevent abuse.
- Output options:
  - Preferred (PostgreSQL): `pg_dump --schema=<tenant_schema> --format=custom` to capture full data/DDL for that tenant.
  - Fallback (SQLite/dev): copy db file or run ORM-based table dumps to CSV bundled in a zip.
- Packaging:
  - Write to `MEDIA_ROOT/backups/<tenant>/<timestamp>/`.
  - Filename format: `<tenant_schema>_<timestamp>.dump` (or .zip).
  - Create `manifest.json` with schema name, row counts (optional), checksum, version, creator, and encryption metadata.
- Delivery: 
  - Store locally on server.
  - Provide secure download link in UI (`/backups/download/<job_id>/`).
  - Optionally push to configured cloud destination.

## Automated backups (nightly)
- Scheduler: Celery Beat entry (`CRON: 02:30 local`) → task `backups.tasks.run_nightly_backups()`.
- Flow:
  1. Iterate active tenants in batches to avoid long transactions; lock per tenant with Redis lock to prevent overlap.
  2. For each, run the same pg_dump pipeline, stream to temp file, encrypt, upload, and record metadata.
  3. Apply retention (e.g., keep last 7 successful per tenant locally and remotely).
- Storage targets: start with local disk; optionally S3-compatible storage via `boto3`, GCS via `google-cloud-storage`, or Google Drive/Dropbox via OAuth tokens stored in a `BackupDestination` model.
- Notifications: email/slack on failures; dashboard widget listing last backup time per tenant.

## Models / settings to add
- `BackupJob` (per run): `tenant`, `requested_by`, `status (pending|running|success|failed)`, `kind (manual|auto)`, `mode (pg_dump|csv_zip|json)`, `storage (local|s3|gdrive|dropbox)`, `file_path`, `file_size`, `checksum`, `encryption (none|fernet|zip-pw)`, `error`, `started_at`, `completed_at`.
- `BackupPreference`: `tenant`, `frequency (daily|weekly|manual)`, `destination (FK)`, `notify_emails`, `retain_days`.
- `BackupDestination`: `type (local|s3|gcs|gdrive|dropbox)`, `config JSON` (bucket, folder, credentials token reference), `is_active`.
- Settings: env vars for pg_dump path, temp dir, default retention, encryption key salt/KEK, and cloud creds.

## Security & privacy
- Enforce org-admin permissions for all manual exports/backups; log audit events with user id, tenant, dataset, and IP.
- Encrypt backups at rest; never store raw cloud credentials in plain text—use env or vault-backed secrets.
- Redact PII from quick exports if policy requires; alternatively tag columns as PII and allow opt-in.
- Sign download URLs (short TTL) and avoid exposing storage paths directly.

## Restore approach (admin/support only)
- Management command `python manage.py restore_tenant_backup --tenant=<code> --file=<path>` that:
  1. Validates checksum and decrypts to temp.
  2. For Postgres: create schema if missing, drop existing objects in target schema, run `pg_restore --schema=<schema>`.
  3. For JSON/CSV bundle: truncate tenant tables and bulk load in dependency order.
- Guardrails: dry-run flag, require explicit `--force`, and disallow restoring to a different tenant without `--allow-override`.

## Testing plan
- Unit-test export service for CSV/XLSX column mapping and content types.
- Integration-test `pg_dump` path with a disposable schema and sample data; verify restore symmetry.
- Celery task tests with mocked storage to ensure retention and locking work.
- Security tests: permission checks, encrypted output verification, and signed URL expiry.

## Next implementation steps (suggested order)
1) Build `backups` app with models above + migrations.
2) Add export service + endpoints for key datasets, reusing existing CSV patterns.
3) Add Celery tasks and beat schedule for nightly backups; wire pg_dump + encryption + local storage.
4) Add optional S3/GDrive destinations and retention cleanup.
5) Ship admin UI: export page, backup status list, manual "Backup My Data" trigger, destination settings.
6) Add restore command with strong safeguards; document operator runbook.