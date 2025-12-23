# Himalytix ERP

Multi-tenant ERP platform focused on accounting, inventory, and user-management for SMEs. The project ships a modern voucher-entry experience, tenant-aware APIs, and opinionated defaults for Nepal-focused deployments.

## Highlights

- **Accounting** – Advanced journal entry grid with voucher templates, posting workflow, and depth-checked chart of accounts. Includes configuration-driven voucher entry UI via the `voucher_config` app.
- **Inventory** – Product catalog, warehouses, batches/serials, and inventory snapshots that tie back to GL accounts.
- **Multi-tenancy & Security** – Tenant middleware, scoped permissions, DRF authentication, and hardened session management.
- **APIs & Automation** – Versioned REST API under `/api/v1/` with OpenAPI docs served via DRF Spectacular at `/api/docs`.

See the high-level architecture (`Docs/architecture.png`) for module boundaries and request flow.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `ERP/` | Django project (settings in `dashboard/`, apps under `accounting`, `Inventory`, `usermanagement`, etc.) |
| `Docs/` | Product & platform documentation, including the architecture diagram |
| `journal_entry_replace_pack/` | Legacy replacement bundle used during voucher-entry migration |
| `.venv/` | (Optional) Local virtual environment (ignored in git) |

## Getting Started

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or set `USE_SQLITE=1` for quick local work)
- Redis (optional but recommended for cache/rate limiting)

Optional OCR helpers (for the mocked receipt workflow) live behind standard Python packages. If you want the logs to stop warning about missing OCR modules or plan to wire in real OCR results, install:

```
pip install pytesseract opencv-python pillow numpy
```

Without them the service stays in mock mode and emits a single warning during startup/tests.

### 2. Clone & Bootstrap

```bash
git clone https://github.com/<your-org>/Himalytix.git
cd Himalytix
python -m venv .venv
.venv\Scripts\activate   # PowerShell
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp ERP/.env.example ERP/.env
# Update DB credentials, Redis URL, and secrets inside ERP/.env
```

Key variables (see `ERP/dashboard/settings.py` for fallbacks):

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | Django secret key |
| `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD` | Postgres connection |
| `USE_SQLITE` | Set to `1` to force SQLite for demos |
| `REDIS_URL` | Redis cache endpoint |
| `COA_MAX_DEPTH / COA_MAX_SIBLINGS` | Chart-of-account guardrails |

### 4. Run Migrations & Start Services

```bash
cd ERP
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

To pick an active organization after login, visit `/manage/select-organization/`.

## LPG / NOC distribution vertical

- Feature toggles per company via `CompanyConfig` (seeded on Organization create).
- Masters: cylinder types/SKUs, dealers, transport providers/vehicles, LPG products, conversion rules.
- Posting flows: NOC purchase allocation + GL, sales with dealer credit enforcement + stock movements, logistics trips with optional transfer/expense posting.
- APIs exposed under `/api/lpg/` with DRF schema coverage; see `ERP/docs/verticals/lpg_pfg.md` for endpoints and setup.
- Basic PWA assets live at `static/pwa/manifest.json` and `static/pwa/service-worker.js`.

## API & Tooling

- **REST API:** All public endpoints are namespaced under `/api/v1/`.
- **Docs & Explorer:** OpenAPI schema at `/api/schema/` and interactive Swagger UI at `/api/docs/`.
- **Authentication:** DRF token auth and session auth; see `api/authentication.py`.
- **Testing:**
	- Full suite: `python manage.py test` (set `PG*` variables or `USE_SQLITE=1`).
	- Phase 2 accounting smoke: `python manage.py test accounting.tests.test_phase2_views accounting.tests.test_models --noinput`.
	- Use `USE_SQLITE=1` for fastest local runs; Postgres-backed runs require the same extensions as production (uuid-ossp, pgcrypto).
- **Linting:** `ruff`, `black`, `isort`, and `flake8` are configured via `pyproject.toml` / `setup.cfg`.

## Developing Features

1. Create a feature branch: `git checkout -b feat/<short-description>`
2. Keep commits conventional (e.g., `feat(accounting): add revaluation job`)
3. Run `python manage.py test` and lint before pushing
4. See `ERP/CONTRIBUTING.md` for the full contribution workflow and PR checklist

## Tenant Branding (Favicons)

- **Admin UI:** In Django admin, open `Tenant branding settings` to pick a tenant and paste an absolute URL or `/static/...` path for the favicon. Leaving the field blank deletes the override and the default icon in `static/images/favicon.ico` is used.
- **Management command:** Configure the same data from the CLI:

	```powershell
	cd ERP
	python manage.py set_tenant_favicon TENANT_CODE --url /static/images/tenant-a.ico
	python manage.py set_tenant_favicon TENANT_CODE --clear  # remove the override
	```

	The command accepts a tenant code, slug, or UUID and persists the value in `TenantConfig (branding.favicon_url)`.

## Architecture Overview

![Architecture Diagram](Docs/architecture.png)

> The diagram highlights traffic flow from the browser/UI through Django (dashboard, accounting, inventory, APIs), tenant-aware middleware, and supporting services (Postgres, Redis, Celery, background jobs).

## Support & Docs

- Product planning and next actions live in `Docs/consolidated_todo_register.md`
- Module-specific READMEs exist under `ERP/<app>/README.md`
- For security issues, email `security@himalytix.com`

Happy building! 🎉
