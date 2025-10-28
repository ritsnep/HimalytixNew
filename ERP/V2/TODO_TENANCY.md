# TODO — Tenancy Propagation

Goal: Ensure every Streamlit → Django call is scoped to the active tenant, matching current middleware behavior.

Contracts
- [ ] `ActiveTenantMiddleware` expects tenant id from session or `HTTP_X_TENANT_ID`.
- [ ] For V2, Streamlit must explicitly send `X-Tenant-ID: <id>` on every request.
- [ ] Token payload also includes `tenant_id` and must match `X-Tenant-ID` (defense‑in‑depth).

Tasks — Django
- [ ] Add `HasActiveTenant` DRF permission to verify both: header present and matches token payload.
- [ ] Extend `ActiveTenantMiddleware` to prefer token claims when DRF auth succeeds.
- [ ] Add unit tests: missing header, mismatched header, unknown tenant id.

Tasks — Streamlit
- [ ] On startup, call `api/v1/auth/streamlit/verify/` to pull canonical `tenant_id` and store in session state.
- [ ] Attach `X-Tenant-ID` to all API requests.
- [ ] Add a simple tenant switcher (optional, if user can change tenant) hitting the existing Django switch endpoint, then refresh token.

Observability
- [ ] Add log fields: `tenant_id`, `ui_channel: streamlit_v2` in Django structured logs for V2 endpoints.

