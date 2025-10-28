# TODO (Master) — Streamlit V2 at /V2

This is the master checklist for delivering the Streamlit V2 UI at `/V2` alongside the existing Django app.

Milestones
- [ ] M0: Skeleton Streamlit app runs locally behind `/V2`
- [ ] M1: Secure auth bridge (short‑lived token) with tenant context
- [ ] M2: Core analytics pages (Dashboards, Trial Balance, Ledger Explorer)
- [ ] M3: Voucher flows (read‑only list + details, then create/post)
- [ ] M4: Observability (metrics, tracing, logs correlation)
- [ ] M5: Harden (security headers, rate limits, cache)
- [ ] M6: CI/CD + deployment

Scope (high level)
- [ ] Streamlit service scaffold (`pages/` with routing)
- [ ] Auth handshake (Django → signed session token → Streamlit)
- [ ] Tenancy propagation (`X-Tenant-ID` enforced end to end)
- [ ] DRF APIs for V2 (optimized list, summaries, exports)
- [ ] Security and headers (CSP, frame policy, rate limiting parity)
- [ ] Deployment (Docker Compose, Nginx reverse proxy, health)
- [ ] Observability (Prometheus, traces, structured logs)

References
- See `TODO_AUTH.md`, `TODO_TENANCY.md`, `TODO_API.md`, `TODO_SECURITY.md`, `TODO_DEPLOY.md`, `TODO_OBSERVABILITY.md`, `TODO_UI.md` for details.

