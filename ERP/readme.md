# ERP Project

This Django project loads configuration from environment variables. When a variable is missing a development-friendly default is used.
# ERP Project

This repository contains a Django-based ERP system composed of several interrelated apps.

## Applications

## Management Commands

### initialize_system

```
python manage.py initialize_system

## Required environment variables

- `DJANGO_SECRET_KEY` – secret key for Django. Defaults to the value in `dashboard/settings.py` if unset.
- `DB_ENGINE` – database engine, defaults to `mssql`.
- `DB_NAME` – database name, defaults to `erptest1`.
- `DB_USER` – database user, defaults to `erpuser`.
- `DB_PASSWORD` – database password, defaults to `user@123`.
- `DB_HOST` – database host, defaults to `localhost`.
- `DB_PORT` – database port, defaults to `1433`.
- `DB_DRIVER` – ODBC driver string, defaults to `ODBC Driver 17 for SQL Server`.
- `DB_TRUSTED_CONNECTION` – set to `yes` or `no`; defaults to `no`.

Create an `.env` file or export variables in your shell before running `manage.py`.


### dashboard
Central Django project that holds settings and URL configuration. It includes the multi-tenant middleware and routes to the other apps.

### usermanagement
Handles authentication, organizations, roles and permissions. The `CustomUser` model extends Django's `AbstractUser` and stores a `role` field (`superadmin`, `admin`, `user`). Management commands under `usermanagement/management/commands/` generate permissions and set up default roles.

### tenancy
Provides tenant models and middleware. Each request is associated with a tenant and the middleware adjusts the database schema accordingly.

### accounting
Implements core accounting functionality including fiscal years, chart of accounts and journals. Models reference the organizations defined in `usermanagement`.

### api
Contains REST API endpoints (currently minimal) built with Django REST Framework.

## Setup

1. Install dependencies (inside a virtual environment is recommended):
   ```bash
   pip install -r ERP/requirements.txt
   ```
2. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
3. Initialize the system and create the default admin account:
   ```bash
   python manage.py initialize_system
   ```
   This command generates permissions, sets up the default roles and creates the initial administrator.
4. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Default Roles and Permissions

`setup_default_roles` creates two organization‑level roles:

- **Administrator** – assigned all generated permissions providing full access to every module.
- **User** – granted only the `view` actions for each entity.

The built‑in `Super Admin` role on `CustomUser` bypasses normal permission checks. Users are linked to organizations through the `UserRole` model and inherit permissions from their assigned roles.


## Overview

This repository contains a Django-based Enterprise Resource Planning (ERP) system. It provides modules for accounting, user management and exposes a REST API for integration with other services.

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