# TODO — Checkpoints & Acceptance Criteria

M0 — Skeleton
- [ ] `/V2` renders Streamlit shell with sidebar and token bootstrap.
- [ ] Token appears valid via `verify` endpoint; URL sanitized post‑bootstrap.

M1 — Auth + Tenancy
- [ ] All API calls include `Authorization` and `X-Tenant-ID`.
- [ ] Mis‑matched tenant rejected with 403 and logged.

M2 — Core Analytics
- [ ] Dashboard cards and 2 charts render within SLA (<1.5s) on seeded data.
- [ ] Trial Balance filters and export work; pagination OK.

M3 — Vouchers (Read‑only)
- [ ] Voucher list with filters, sorting; detail view loads lines.

M4 — Security & Perf
- [ ] Rate limits applied; CSP verified; no mixed content.
- [ ] p95 latency < 800ms for list endpoints under nominal load.

M5 — Observability
- [ ] Metrics and traces visible; logs include `tenant_id` and `ui_channel`.

M6 — CI/CD
- [ ] Images built; smoke passes; rollback guide updated.

