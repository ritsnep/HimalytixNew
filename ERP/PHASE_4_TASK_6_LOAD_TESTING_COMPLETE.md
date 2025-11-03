<<<<<<< ours
# Phase 4 Task 6 – Load Testing & Performance Tuning

Status: Complete

This task adds a production-ready load testing harness (Locust), Make targets for easy runs, and guidance for baseline and follow-up tuning. It complements our earlier caching and observability work.

## What we delivered

- Load test suite in `ERP/load_tests/` with realistic scenarios:
  - UI browse: `/` and `/dashboard/`
  - Journal Entries API: list, create, get, update, delete
  - Reporting API: monthly CSV
  - Search API: keyword queries
- Auth support via API key or JWT login
- Makefile targets: `make locust` (UI) and `make locust-headless` (CSV output)
- `.gitignore` for result artifacts, Windows-friendly README with steps
- Enabled `GZipMiddleware` for response compression to improve bandwidth usage and tail latencies

## Run a baseline (Windows PowerShell)

```powershell
# Create and activate virtualenv (if needed)
python -m venv .venv
. .venv\Scripts\Activate.ps1

# Install Locust deps
pip install -r ERP\load_tests\requirements.txt

# Optional auth env vars
$env:LOCUST_API_KEY = "<your-api-key>"
# or
# $env:LOCUST_USERNAME = "admin"; $env:LOCUST_PASSWORD = "adminpass"

# Start headless baseline (10 minutes)
cd ERP
locust -f load_tests\locustfile.py --host http://localhost:8000 -u 200 -r 20 -t 10m --csv results\baseline
```

Collect CSVs under `ERP\load_tests\results\baseline*`. For interactive runs, open the Web UI:

```powershell
cd ERP
locust -f load_tests\locustfile.py --host http://localhost:8000
```

## What to measure

- p95 response time (goal: < 500ms)
- Error rate (goal: < 0.1%)
- Throughput (stretch: ~1000 req/s with horizontal scale)
- Hot endpoints and N+1 query patterns (via Silk and Prometheus/Grafana)

## Tuning notes (applied and available)

- Database:
  - Persistent connections `CONN_MAX_AGE=600` (already configured)
  - Set `statement_timeout=30s` (already configured)
  - Add indexes on frequently filtered columns (journal entries, search)
- Caching:
  - Page/fragment/API caching utilities added in Phase 4 Task 5
  - Run `python manage.py warm_cache --scope all` pre-test to simulate warm traffic
- Compression:
  - Enabled `GZipMiddleware` to reduce payload size and tail latencies
- App/Infra:
  - Avoid N+1; batch queries; select/prefetch related
  - Scale app workers based on CPU and I/O; set reasonable timeouts

## Results summary (fill after runs)

- Baseline (date/time, env):
  - RPS: ____
  - p95: ____ ms
  - Errors: ____ %
- After tuning (date/time, env):
  - RPS: ____
  - p95: ____ ms
  - Errors: ____ %

## Follow-ups

- Commit DB indexes identified from EXPLAIN ANALYZE on hot queries
- Add scenario-specific thresholds (fail build on regressions) if integrating into CI
=======
# Phase 4 Task 6 – Load Testing & Performance Tuning

Status: Complete

This task adds a production-ready load testing harness (Locust), Make targets for easy runs, and guidance for baseline and follow-up tuning. It complements our earlier caching and observability work.

## What we delivered

- Load test suite in `ERP/load_tests/` with realistic scenarios:
  - UI browse: `/` and `/dashboard/`
  - Journal Entries API: list, create, get, update, delete
  - Reporting API: monthly CSV
  - Search API: keyword queries
- Auth support via API key or JWT login
- Makefile targets: `make locust` (UI) and `make locust-headless` (CSV output)
- `.gitignore` for result artifacts, Windows-friendly README with steps
- Enabled `GZipMiddleware` for response compression to improve bandwidth usage and tail latencies

## Run a baseline (Windows PowerShell)

```powershell
# Create and activate virtualenv (if needed)
python -m venv .venv
. .venv\Scripts\Activate.ps1

# Install Locust deps
pip install -r ERP\load_tests\requirements.txt

# Optional auth env vars
$env:LOCUST_API_KEY = "<your-api-key>"
# or
# $env:LOCUST_USERNAME = "admin"; $env:LOCUST_PASSWORD = "adminpass"

# Start headless baseline (10 minutes)
cd ERP
locust -f load_tests\locustfile.py --host http://localhost:8000 -u 200 -r 20 -t 10m --csv results\baseline
```

Collect CSVs under `ERP\load_tests\results\baseline*`. For interactive runs, open the Web UI:

```powershell
cd ERP
locust -f load_tests\locustfile.py --host http://localhost:8000
```

## What to measure

- p95 response time (goal: < 500ms)
- Error rate (goal: < 0.1%)
- Throughput (stretch: ~1000 req/s with horizontal scale)
- Hot endpoints and N+1 query patterns (via Silk and Prometheus/Grafana)

## Tuning notes (applied and available)

- Database:
  - Persistent connections `CONN_MAX_AGE=600` (already configured)
  - Set `statement_timeout=30s` (already configured)
  - Add indexes on frequently filtered columns (journal entries, search)
- Caching:
  - Page/fragment/API caching utilities added in Phase 4 Task 5
  - Run `python manage.py warm_cache --scope all` pre-test to simulate warm traffic
- Compression:
  - Enabled `GZipMiddleware` to reduce payload size and tail latencies
- App/Infra:
  - Avoid N+1; batch queries; select/prefetch related
  - Scale app workers based on CPU and I/O; set reasonable timeouts

## Results summary (fill after runs)

- Baseline (date/time, env):
  - RPS: ____
  - p95: ____ ms
  - Errors: ____ %
- After tuning (date/time, env):
  - RPS: ____
  - p95: ____ ms
  - Errors: ____ %

## Follow-ups

- Commit DB indexes identified from EXPLAIN ANALYZE on hot queries
- Add scenario-specific thresholds (fail build on regressions) if integrating into CI
>>>>>>> theirs
