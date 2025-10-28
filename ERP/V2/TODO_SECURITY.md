# TODO — Security & Headers

Goal: Match Django security posture for `/V2` and API calls without breaking Streamlit.

Headers
- [ ] Review `SecurityHeadersMiddleware` for CSP compatibility with Streamlit assets.
- [ ] Update CSP to allow Streamlit path if necessary: scripts/styles from same origin; consider websocket endpoints.
- [ ] Keep `X-Frame-Options: DENY` (no iframes). Avoid embedding Streamlit in iframes.

Rate Limiting
- [ ] Extend `RateLimitMiddleware` groups to include `/V2` token issue/verify endpoints.
- [ ] Add per‑user limits for heavy analytics endpoints (e.g., trial balance) to prevent abuse.

Tokens
- [ ] Short TTL, rotate on page loads, reject reuse after expiry.
- [ ] Include `tenant_id` in claims; validate header vs claims.
- [ ] Log token issuance with `user_id`, `tenant_id`, `expires_at` (no token bodies in logs).

Transport
- [ ] Enforce HTTPS in all environments; HSTS remains enabled.

Secrets
- [ ] No tokens in HTML or logs; query param removed ASAP.

