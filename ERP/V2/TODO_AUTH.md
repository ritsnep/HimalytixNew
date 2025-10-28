# TODO — Auth Bridge (Django ⇄ Streamlit)

Goal: Allow a logged‑in Django user to use Streamlit at `/V2` and make authenticated API calls back to Django with tenant context, without duplicating auth logic.

Design
- [ ] Use `django.core.signing` (TimestampSigner) to mint short‑lived signed tokens containing: `sub` (user id), `username`, `tenant_id`, `issued_at`, `expiry`.
- [ ] Token TTL: 10 minutes default; refresh allowed via silent redirect.
- [ ] Pass token to Streamlit initially via query param `?st=<token>` (simple track) and sanitize URL after bootstrap.
- [ ] Streamlit stores token in `st.session_state['token']` and attaches `Authorization: Bearer <token>` to all requests to Django.
- [ ] Django DRF custom auth class validates signed tokens and maps to `request.user` + `request.tenant`.

Tasks — Django
- [ ] Add `api/v1/auth/streamlit/verify/` to validate tokens (returns user + tenant info, expiry) for diagnostics.
- [ ] Add `api/v1/auth/streamlit/issue/` view to issue tokens for current session (login required). Alternate: issue inside a small HTML handler used by proxy.
- [ ] Implement `StreamlitTokenAuthentication` (DRF) using TimestampSigner, reject expired or tampered tokens.
- [ ] Gate V2 endpoints with `IsAuthenticated` + custom `HasActiveTenant` permissions.
- [ ] Add rate limits to `issue/verify` endpoints (middleware already supports grouping by path).

Tasks — Streamlit
- [ ] Bootstrap page: read `st` query param; move it into `st.session_state` and then clear query string via `st.experimental_set_query_params()`.
- [ ] Create a small `ApiClient` wrapper that sets headers: `Authorization: Bearer <token>`, `X-Tenant-ID: <tenant_id>`.
- [ ] Add a token refresh helper that hits `issue/` if nearing expiry and updates session state.

Stretch (Advanced Proxy)
- [ ] Nginx `auth_request` pattern to fetch a token per request and inject as upstream header to Streamlit (keeps token off the URL). Requires a lightweight Django endpoint and Nginx config; optional for v1.

Risks
- [ ] Query param exposure: mitigate via short TTL + remove from URL immediately.
- [ ] Clock skew: allow small leeway (±60s) in validator.

