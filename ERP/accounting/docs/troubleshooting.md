# Voucher Entry — Troubleshooting & Debugging

This page lists common problems and steps to debug HTMX-based interactions.

1) "Click Add Line and nothing happens"
- Check browser console for errors (F12 → Console). Look for `htmx:responseError` or JS exceptions.
- Open Network tab: verify POST to `/accounting/journal-entry/add-row/` returned 200 and HTML. If you see 403, likely CSRF/auth issue.
- The dev page includes a flash on `htmx:afterSwap`. If you see the green flash, the swap executed.

2) Server returns 200 but row HTML isn't visible
- Confirm the HTMX swap target is correct (e.g., `hx-target="#grid-rows"` and `hx-swap="beforeend"`).
- Inspect the returned HTML fragment from the server (Network tab -> Response) — ensure it’s a `<div>` with correct classes and not empty.
- CSS utility classes may hide content if a parent has `overflow: hidden` or `display: none` — inspect DOM for newly appended element.

3) CSRF / authentication errors
- Ensure user is logged in and has the appropriate permissions.
- If HTMX calls show 403, ensure Django CSRF cookie/header is present. Standard Django setup (CsrfViewMiddleware + cookies) works with HTMX.
- If needed, include a meta tag that HTMX can read or set the header manually: `htmx.on('configRequest', (evt) => evt.detail.headers['X-CSRFToken'] = getCookie('csrftoken'))`.

4) Account lookup returning legacy dropdown or wrong HTML
- The `account_lookup` handler returns either `<option>` elements (for select replacements) or legacy dropdown items depending on request headers. For HTMX selects, ensure request includes `HX-Request` header (HTMX sets this automatically).

5) Missing static assets or Tailwind not applied
- Check that `voucher_entry_new.html` includes Tailwind CDN and that CSS isn’t being overridden by other global styles.

6) How to get more verbose server logs
- In `settings.py`, set `LOGGING` to `DEBUG` level for `accounting` module or run the dev server with `--verbosity=2`.

Contact
- If you hit an edge case not covered here, collect the following and open an issue:
  - Browser console logs
  - Network request/response for the failing HTMX call
  - Server logs around the request timestamps
  - A minimal reproduction or steps to reproduce
