# Load Testing with Locust

This folder contains load testing scenarios for the Himalytix ERP using Locust.

## Installation

PowerShell (Windows):

```powershell
# Create and activate venv if needed
python -m venv .venv
. .venv\Scripts\Activate.ps1

# Install locust
pip install -r load_tests\requirements.txt
```

## Environment Variables

Set these before running (optional depending on your auth):

- `LOCUST_API_KEY` - API key for header auth
- `LOCUST_USERNAME` - Username for JWT login
- `LOCUST_PASSWORD` - Password for JWT login
- `LOCUST_TENANT_ID` - Tenant header

PowerShell example:

```powershell
$env:LOCUST_USERNAME = "admin"
$env:LOCUST_PASSWORD = "adminpass"
$env:LOCUST_TENANT_ID = "1"
```

## Run (Web UI)

```powershell
# From repo root or ERP folder
cd ERP
locust -f load_tests\locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 and enter users and spawn rate, e.g.:
- Users: 100
- Spawn rate: 10

## Run (Headless)

```powershell
locust -f load_tests\locustfile.py --host http://localhost:8000 -u 200 -r 20 -t 10m --csv results\himalytix
```

CSV results will be stored under `results/`.

## Scenarios Included

- Browse UI: `/` and `/dashboard/`
- Journal Entries API: list, create, get, update, delete
- Reporting API: monthly report (CSV)
- Search API: query endpoint

Adjust endpoints in `locustfile.py` to match your installation.

## Suggested Goals (per instance)

- p95 response time < 500ms
- Error rate < 0.1%
- Throughput: 1000 req/sec sustained

## Tips

- Run in staging with realistic data
- Warm caches before testing: `python manage.py warm_cache --scope all`
- Monitor with Grafana dashboards added in Phase 4
- Profile slow endpoints with django-silk (`/silk/`)
