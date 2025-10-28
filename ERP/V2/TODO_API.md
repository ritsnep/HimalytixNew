# TODO — DRF Endpoints for V2

Goal: Provide fast, tenant‑safe endpoints tailored for Streamlit charts, tables, and voucher flows.

General
- [ ] Add versioned routes under `api/v1/v2/` to keep semantics explicit.
- [ ] Use select_related/prefetch_related and pagination defaults tuned for Streamlit.
- [ ] Add `Cache-Control` guidance for read‑heavy endpoints (short TTL, tenant‑scoped).

Analytics
- [ ] `GET api/v1/v2/metrics/summary` — cards: balances, counts, period deltas.
- [ ] `GET api/v1/v2/trial-balance` — period, level, zero filters; CSV export.
- [ ] `GET api/v1/v2/ledger-explorer` — account filter, date range, pagination.
- [ ] `GET api/v1/v2/charts/<key>` — optimized datasets for chart blocks (e.g., monthly income/expense).

Vouchers
- [ ] `GET api/v1/v2/vouchers` — list with status/type filters, server‑side sort/page.
- [ ] `GET api/v1/v2/vouchers/<id>` — details with lines.
- [ ] `POST api/v1/v2/vouchers` — create (phase 2; start read‑only first).
- [ ] `POST api/v1/v2/vouchers/<id>/post` — post workflow with locking, validation.

Auth
- [ ] `POST api/v1/auth/streamlit/issue` — returns short‑lived signed token.
- [ ] `POST api/v1/auth/streamlit/verify` — validate token, return claims.

Performance
- [ ] Ensure relevant DB indexes exist for date/status/tenant filters (see existing 0099/0103/0104 migrations).
- [ ] Use serializer `.only()` / `.values()` where rendering large lists.
- [ ] Add `limit` caps server‑side to protect from abusive queries.

Testing
- [ ] Unit tests for each endpoint (permissions, tenancy, pagination, invalid params).
- [ ] Integration tests: end‑to‑end with signed token and `X-Tenant-ID`.

