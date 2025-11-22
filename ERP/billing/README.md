# Billing (IRD e-billing) Module

This app provides Nepal IRD-compliant billing with immutable invoices, sequential numbering, audit logging, credit/debit notes, and CBMS sync hooks.

## Key concepts
- **InvoiceSeries**: tracks the last number per tenant + fiscal year; used to generate sequential invoice numbers like `2078-000123`.
- **InvoiceHeader/InvoiceLine**: immutable once created; corrections are captured via **CreditDebitNote**.
- **InvoiceAuditLog**: every create/cancel/note/sync action is recorded for IRD auditability.
- **CBMS client**: `billing.services.CBMSClient` serializes invoices and sends them to IRD; `resync_invoices` retries failures.

## Usage
- Add `billing` to `INSTALLED_APPS` (already done) and run migrations.
- Create invoices via `/billing/invoices/` (nested lines supported). Cancelling an invoice (`POST /billing/invoices/{id}/cancel`) creates a credit note and marks the invoice canceled.
- Management commands:
  - `python manage.py resync_invoices` — resend failed CBMS submissions.
  - `python manage.py assign_billing_permissions` — seed permissions onto roles/groups.

## Environment
- `CBMS_API_URL`, `CBMS_API_KEY` — CBMS endpoint and API key.
- `BILLING_FISCAL_YEAR` — optional override for fiscal year code.
- `ENABLE_STRICT_SECURITY=1` — turn on SSL/HSTS/cookie hardening in production.

## Testing
- Unit/API tests live in `billing/tests/` (sequence generation, immutability, cancel flow). Mock CBMS when running integration tests.
