# TODO — Streamlit UI Pages

Goal: Ship a cohesive Streamlit UI under `/V2` with production hygiene.

Structure
- [ ] App root: `app.py` (theme, sidebar, token bootstrap, tenant banner)
- [ ] Pages dir: `pages/`
  - [ ] `00_Dashboard.py`
  - [ ] `10_Trial_Balance.py`
  - [ ] `20_Ledger_Explorer.py`
  - [ ] `30_Vouchers_List.py` (read‑only first)
  - [ ] `31_Voucher_Detail.py` (read‑only first)
  - [ ] `99_Settings.py` (tenant switch, token diagnostics)

Components
- [ ] `lib/api_client.py` — requests wrapper with auth + tenant headers
- [ ] `lib/charts.py` — Chart.js/ECharts helpers (prefer lazy loaded via `components.html`)
- [ ] `lib/tables.py` — compact table helper (pandas render or lightweight aggrid)
- [ ] `lib/state.py` — token, tenant, user session helpers

UX/Polish
- [ ] Dark/light theme aligned with Django theme
- [ ] Compact density tables, keyboard nav where sensible
- [ ] Empty‑state and error surfaces for each page
- [ ] Loading spinners and cached queries (`st.cache_data` with TTL)

Security in UI
- [ ] Remove token from URL immediately after bootstrap
- [ ] Gate all data calls on token presence/validity

Testing
- [ ] Smoke script to hit each page and validate main widgets
- [ ] Contract tests to ensure API shapes match expectations

