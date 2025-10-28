# TODO — Deployment & Reverse Proxy

Docker / Services
- [ ] Add `streamlit` service to `docker-compose.yml` with healthcheck.
- [ ] Separate `V2/requirements.txt` (optionally) with `streamlit`, `requests`, and minimal deps.
- [ ] Parameterize with env vars: `V2_PORT`, `DJANGO_API_BASE`, `TOKEN_ISSUER_URL`.

Reverse Proxy (Nginx/Traefik)
- [ ] Map `/V2` → Streamlit container (`/` on :8501).
- [ ] Option A (simple): Django issues token link; proxy passes request through untouched.
- [ ] Option B (advanced): Use `auth_request` to Django to fetch a short‑lived token and append `?st=<token>` or inject an upstream header to Streamlit.
- [ ] Ensure websocket upgrade for Streamlit.

Django Integration
- [ ] Add `/health/streamlit` endpoint if needed for orchestrator readiness.
- [ ] Optional: add a thin landing at `/V2/` that redirects to `/V2?st=<token>` when accessed without token.

Security
- [ ] CSP allowlist for Streamlit assets under same origin path; verify no external CDNs are required.
- [ ] Keep HSTS and security headers at the edge.

CI/CD
- [ ] Build/push `streamlit` image; run smoke script against `/V2`.

