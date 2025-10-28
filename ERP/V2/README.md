# V2 Streamlit UI (at /V2)

This directory tracks the plan and task lists for the Streamlit-powered V2 UI served under the `/V2` path. The V2 UI complements the existing Django+HTMX app and focuses on analytics, dashboards, and high‑interactivity flows.

- Master checklist: `ERP/V2/TODO.md`
- Focused checklists: auth, tenancy, API, security, deployment, observability, and UI pages.

Assumptions
- Reverse proxy maps `/V2` to the Streamlit server.
- Short‑lived, signed tokens bridge Django session → Streamlit backend API calls.
- Requests from Streamlit to Django carry `X-Tenant-ID` derived from Django session context.

Local dev quick start
- Install deps: `pip install -r ERP/V2/requirements.txt`
- Run Streamlit: `streamlit run ERP/V2/app.py --server.port 8501 --server.baseUrlPath V2`
- Log in to Django, then open: `http://localhost:8000/V2/login` → redirects to `/V2?st=<token>` which boots the app and removes the token from URL.
