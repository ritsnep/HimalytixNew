# Himalytix ERP

[![CI Pipeline](https://img.shields.io/github/actions/workflow/status/himalytix/erp/ci.yml?branch=main&label=CI)](https://github.com/himalytix/erp/actions)
[![Coverage](https://img.shields.io/codecov/c/github/himalytix/erp?token=YOUR_TOKEN)](https://codecov.io/gh/himalytix/erp)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENCE.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-5.1+-green.svg)](https://www.djangoproject.com/)

Multi-tenant ERP system for the Nepal market, built with Django, HTMX, Alpine.js, and PostgreSQL.

## 🎯 Features

- **Multi-Tenancy**: Schema-based isolation for complete data security
- **Accounting**: Chart of Accounts, Journal Entries, Ledger, Financial Reports
- **Inventory Management**: Stock tracking, purchase orders, sales orders
- **User Management**: Role-based access control (RBAC), organizations, permissions
- **Internationalization**: English + Nepali (Devanagari), RTL support, locale-aware formatting
- **RESTful API**: Django REST Framework with token authentication
- **Forms Designer**: Dynamic form builder for custom data collection
- **Modern UI**: HTMX + Alpine.js for reactive interfaces, Tailwind CSS styling

## 📋 Prerequisites

- **Python**: 3.11 or higher
- **PostgreSQL**: 14 or higher (recommended for production)
- **Redis**: 7+ (for Celery task queue)
- **Node.js**: 18+ (for Webpack/Tailwind builds, optional)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/himalytix/erp.git
cd erp
```

### 2. Create Virtual Environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings (boolean flags accept `1/0`, `true/false`, or `on/off`):

```env
# Django
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
SECURE_SSL_REDIRECT=0  # force HTTPS in production
SESSION_COOKIE_SECURE=0
CSRF_COOKIE_SECURE=0
ACCOUNT_ALLOW_SIGNUP=0

# Database (PostgreSQL recommended)
DB_ENGINE=postgresql
DB_NAME=erpdb
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
```

The project loads `.env` automatically via `python-dotenv`, so these values override system settings for every `manage.py` command.

**Security Note**: Generate a secure secret key:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 5. Database Setup

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# (Optional) Load demo data
python manage.py loaddata fixtures/demo_data.json
```

### 6. Run Development Server

```bash
# Start Django
python manage.py runserver

# In another terminal: Start Celery (for async tasks)
celery -A dashboard worker -l info
```

Visit: **http://localhost:8000**

## UI Building Blocks

### components/base/list_base.html

- Shared layout for list/index pages, wrapping DataTables, export buttons, responsive layout, and a collapsible filter drawer that plays nicely with HTMX updates.
- **Inputs**: page_title, list_title, readcrumbs, create_url, create_button_text, datatable_config (JSON block), list_shortcuts (JSON block), ilter_drawer_id, datatable_id, and optional quick_search_placeholder.
- **Blocks**: list_page_title, list_title, list_actions, list_header_extras, list_quick_filters, list_filters, 	able_head, 	able_body, 	able_foot, list_before_table, list_after_table, list_extra_js.
- **Keyboard shortcuts** via static/js/list-base.js: / focuses search, Ctrl+Shift+F toggles filters, Ctrl+Shift+E expands the table, and arbitrary shortcuts can be declared with {"shortcuts": [{"keys": "ctrl+k", "action": "focus", "target": "#global-search"}]} inside the list_shortcuts_id script tag.
- DataTables options are merged from <script type="application/json" id="datatable-config">{ ... }</script> so per-page configs can tweak buttons, AJAX sources, or column definitions without duplicating JS.

### components/base/form_base.html

- Shared shell for CRUD forms: breadcrumb + title bar, sticky action rail, dirty-state indicator, and helpful hotkeys baked in.
- **Inputs**: orm_title, orm_description, orm_subtitle, readcrumbs, orm_method, orm_action, orm_enctype, orm_dom_id, cancel_url, orm_config (JSON block), orm_track_dirty.
- **Blocks**: orm_heading, orm_title_text, orm_intro, orm_alerts, orm_hidden_fields, orm_fields, orm_actions, orm_extra_js.
- **Keyboard shortcuts** via static/js/form-base.js: Ctrl+S saves, Ctrl+Enter submits, Ctrl+Shift+E expands the surface. Provide custom shortcuts by adding {"shortcuts": [{"keys": "ctrl+shift+h", "message": "Help opened"}]} to the orm_config_id JSON block.
- Enhancements: .datepicker fields automatically use Bootstrap Datepicker, .flatpickr variants use Flatpickr, and Pristine.js validates any form marked 
ovalidate unless you set orm_track_dirty=False.

The inventory app is the pilot module already running on these shared components. Other apps can migrate gradually by switching their {% extends %} directives to components/base/list_base.html / components/base/form_base.html, filling the documented blocks, and (optionally) dropping per-page JS in favour of the new helpers.

## 📊 Architecture

### Applications

| App | Purpose | Key Models |
|-----|---------|------------|
| `dashboard` | Main project settings, URL routing | - |
| `usermanagement` | Authentication, organizations, roles | `CustomUser`, `Organization`, `Role` |
| `tenancy` | Multi-tenant middleware, tenant isolation | `Tenant`, `Domain` |
| `accounting` | Chart of Accounts, journals, ledgers | `FiscalYear`, `ChartOfAccount`, `JournalEntry` |
| `inventory` | Stock management, purchase/sales orders | `Item`, `StockMovement`, `PurchaseOrder` |
| `api` | REST API endpoints (v1) | - |
| `forms_designer` | Dynamic form builder | `Form`, `Field` |

### Tech Stack

- **Backend**: Django 5.1.2, Django REST Framework, Celery
- **Frontend**: HTMX 1.9+, Alpine.js 3.x, Tailwind CSS 3.x
- **Database**: PostgreSQL 14+ (SQLite for dev)
- **Cache/Broker**: Redis 7+
- **Observability**: Structlog (JSON logging), Prometheus (metrics at `/metrics`)

See [Architecture Decision Records](docs/adr/) for detailed design decisions.

## 🔒 Security

- **Secret Scanning**: Pre-commit hooks with `detect-secrets`
- **Dependency Scanning**: `pip-audit`, `safety` in CI
- **Code Quality**: Black, Flake8, Bandit (security linter)
- **SBOM**: Software Bill of Materials generated on releases
- **HTTPS**: Enforce SSL in production (`SECURE_SSL_REDIRECT=True`)

## 🧪 Testing

```bash
# Run all tests
python manage.py test

# Run with coverage
coverage run --source='.' manage.py test
coverage report --fail-under=70
coverage html  # Open htmlcov/index.html

# Run specific app tests
python manage.py test accounting
```

## 📦 Deployment

### Production Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set strong `DJANGO_SECRET_KEY`
- [ ] Enable HTTPS (`SECURE_SSL_REDIRECT=True`)
- [ ] Configure email backend (not console)
- [ ] Set up Celery with systemd/supervisor
- [ ] Configure Redis persistence
- [ ] Enable log rotation (`logging.handlers.RotatingFileHandler`)
- [ ] Set up monitoring (Prometheus + Grafana)

### Deploy to Render.com (Staging)

See [.github/workflows/cd.yml](.github/workflows/cd.yml) for automated deployment.

## 🛡️ Maintenance Kill Switch

The `MaintenanceModeMiddleware` protects production during risky deploys:

- State lives in Redis (`maintenance:state`) so multiple app servers stay in sync.
- Environment defaults (`MAINTENANCE_MODE`, `MAINTENANCE_MESSAGE`, etc.) seed the cache, but you can flip the switch live without redeploying.
- Requests are short-circuited with HTTP 503 + friendly HTML/JSON copy. Health checks, `/metrics`, static assets, and optional allowlists continue working.
- In-flight POST/PUT requests capture a lightweight snapshot (`MAINTENANCE_SNAPSHOT_TTL`) so users can resume once maintenance clears.

Basic workflow:

```bash
# Enable maintenance before migrations
python manage.py shell
>>> from utils.maintenance import set_maintenance_state
>>> set_maintenance_state(enabled=True, message="Upgrade in progress", status_text="ETA 5 min")

# Disable when done
python manage.py shell
>>> from utils.maintenance import set_maintenance_state
>>> set_maintenance_state(enabled=False)
```

Tune behavior via `MAINTENANCE_ALLOW_URLS`, `MAINTENANCE_ALLOW_IPS`, `MAINTENANCE_MESSAGE`, `MAINTENANCE_RETRY_AFTER`, and `MAINTENANCE_STREAM_*` env vars documented above.

## 📚 Documentation

- **[Quick Start Guide](QUICK_START_GUIDE.md)**: Detailed setup instructions
- **[API Documentation](API.md)**: REST API reference
- **[Architecture Overview](architecture_overview.md)**: System design
- **[Accounting Architecture](accounting_architecture.md)**: Accounting module details
- **[User Management](usermanagement_architecture.md)**: Auth & permissions
- **[ADRs](docs/adr/)**: Architecture Decision Records
- **[Contributing](CONTRIBUTING.md)**: Development guidelines

## 🛠️ Development

### Install Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

This enables automatic checks on commit:
- Secret scanning (detect-secrets)
- Code formatting (Black, isort)
- Linting (Flake8)
- Conventional commits

### Code Style

- **Python**: Black (line length 100), Flake8, isort
- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
- **Tests**: Minimum 70% coverage required

### Useful Commands

```bash
# Format code
black . --line-length=100

# Lint code
flake8 . --max-line-length=100 --extend-ignore=E203,W503

# Run pre-commit on all files
pre-commit run --all-files

# Collect static files
python manage.py collectstatic --noinput

# Create migrations
python manage.py makemigrations

# Shell with Django context
python manage.py shell
```

## 🌍 Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | - | Django secret key (**required**) |
| `DJANGO_DEBUG` | `False` | Debug mode (set `1` only for local development) |
| `DJANGO_ALLOWED_HOSTS` | `localhost` | Comma-separated allowed hosts |
| `DB_ENGINE` | `postgresql` | Database engine (`postgresql`, `sqlite3`, `mssql`) |
| `DB_NAME` | `erpdb` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | - | Database password |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker URL |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `console` | Log format (`console` or `json`) |
| `SECURE_SSL_REDIRECT` | `True` when not in debug | Enforce HTTPS in production; set `0` locally to avoid redirect loops |
| `SESSION_COOKIE_SECURE` | `True` when not in debug | Serve session cookies only over HTTPS |
| `CSRF_COOKIE_SECURE` | `True` when not in debug | Serve CSRF cookies only over HTTPS |
| `SESSION_COOKIE_SAMESITE` | `Lax` | Adjust to `None` when embedding in other domains |
| `CSRF_COOKIE_SAMESITE` | `Lax` | Match client expectations for cross-site posts |
| `ACCOUNT_ALLOW_SIGNUP` | `0` | Disable self-service signup outside controlled environments |
| `MAINTENANCE_MODE` | `0` | Puts the site behind the maintenance middleware when enabled |
| `MAINTENANCE_MESSAGE` | Friendly default | Copy displayed on maintenance page/broadcasts |
| `MAINTENANCE_RETRY_AFTER` | `300` | Seconds to communicate via `Retry-After` header |
| `MAINTENANCE_ALLOW_URLS` | `/health/,/metrics` | Comma-separated paths that bypass maintenance mode |

See [`.env.example`](.env.example) for complete list.

## 📈 Monitoring

- **Metrics**: http://localhost:8000/metrics (Prometheus format)
- **Logs**: `logs/application.log` (JSON format in production)
- **Health Check**: http://localhost:8000/health/ (TODO: implement)

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Pull request guidelines
- Code style requirements
- Testing standards
- Commit message conventions

## 📄 License

This project is licensed under the MIT License - see [LICENCE.md](LICENCE.md) for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/himalytix/erp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/himalytix/erp/discussions)
- **Documentation**: [docs/](docs/)

## 🗺️ Roadmap

- **Phase 4**: Mobile app (React Native), advanced reporting
- **Phase 5**: AI/ML forecasting, third-party integrations, GRC compliance

See [PHASE_4_ROADMAP.md](PHASE_4_ROADMAP.md) and [PHASE_5_ROADMAP.md](PHASE_5_ROADMAP.md) for details.

---

**Built with ❤️ for the Nepal market**
   pip install -r ERP/requirements.txt
   ```
2. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
3. Seed baseline data (superuser, roles, permissions, demo ledgers, inventory, LPG, etc.):
   ```bash
   python manage.py seed_database
   ```
   This management command wraps `scripts/seed_database.py` and is idempotent, so it can be safely re-run to refresh defaults.
4. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Default Roles and Permissions

`python manage.py seed_database` provisions the baseline organization-level roles defined in `scripts/seed_database.py`:

- **Administrator** – receives the full generated permission set for every module.
- **User** – limited to the `view` actions for each entity.

The built-in `Super Admin` flag on `CustomUser` still bypasses normal permission checks. Users link to organizations through `UserRole` records and inherit permissions from their assigned roles.


## Overview

This repository contains a Django-based Enterprise Resource Planning (ERP) system. It provides modules for accounting, user management and exposes a REST API for integration with other services.

### Billing module (Nepal IRD)
- New `billing` app delivers sequential invoice numbering, immutable invoice headers/lines, credit/debit notes, and audit logging.
- CBMS client + `resync_invoices` management command support replays of failed submissions.
- Enable via `CBMS_API_URL`, `CBMS_API_KEY`, optional `BILLING_FISCAL_YEAR`, and `ENABLE_STRICT_SECURITY` for production hardening.

## Setup Instructions

1. Ensure Python 3.11 or newer is installed.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r ERP/requirements.txt
   ```
4. Apply migrations and create a superuser:
   ```bash
   python ERP/manage.py migrate
   python ERP/manage.py createsuperuser
   ```
5. Run the development server:
   ```bash
   python ERP/manage.py runserver
   ```
6. Open your browser to `http://localhost:8000/` to access the application.

## Contribution Guidelines

Contributions are welcome! To contribute:

- Fork this repository and create a branch for your changes.
- Follow PEP 8 styling for Python code.
- Include tests where applicable.
- Submit a pull request describing your changes.
