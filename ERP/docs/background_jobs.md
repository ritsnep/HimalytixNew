# Background Job Runtime

This project now ships with a first–class Celery stack for long running tasks,
compliance queues, and future automation jobs. The sections below describe how
it is wired in and how to operate it in development or production.

## Stack Overview

- **Broker / cache**: Redis (`REDIS_URL`, defaults to `redis://localhost:6379/0`).
- **Celery broker**: `CELERY_BROKER_URL`, falls back to Redis DB `1` when not
  explicitly provided.
- **Result backend**: `django-celery-results` (set via `CELERY_RESULT_BACKEND = "django-db"`).
- **Scheduler**: `django-celery-beat` with database backed schedules.
- **Observability**: `DJANGO_STRUCTLOG_CELERY_ENABLED = True` enables the same
  structured logging pipeline that the web tier uses. A built-in `heartbeat`
  task is exposed for smoke testing the worker.

Relevant code lives in:

- `dashboard/celery.py` – Celery app bootstrap/autodiscovery hook.
- `dashboard/__init__.py` – imports the Celery app so `celery -A dashboard …`
  works consistently.
- `dashboard/settings.py` – broker/back-end defaults, eager/test switches, beat
  scheduler config, and structlog toggle.

## Installing Dependencies

Run the usual install command to pick up the new packages:

```bash
pip install -r requirements.txt
```

Apply migrations so `django_celery_results` / `django_celery_beat` tables exist:

```bash
python manage.py migrate django_celery_results
python manage.py migrate django_celery_beat
```

## Local Development Commands

### Run the worker

```bash
celery -A dashboard worker -l info
```

### Run the beat scheduler

```bash
celery -A dashboard beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Smoke test the worker

From a Django shell or anywhere Celery is configured:

```python
from dashboard.celery import heartbeat
heartbeat.delay()
```

The task logs a `celery.heartbeat` event via structlog and returns `{"ok": True}`.

## Environment Switches

| Variable | Purpose | Default |
| --- | --- | --- |
| `CELERY_BROKER_URL` | Override broker endpoint. | Derived from `REDIS_URL` (DB `1`). |
| `CELERY_RESULT_BACKEND` | Where task results are stored. | `django-db` |
| `CELERY_TASK_ALWAYS_EAGER` | Run tasks synchronously (useful for tests). | `0` (disabled) |
| `CELERY_TASK_TIME_LIMIT` / `CELERY_TASK_SOFT_TIME_LIMIT` | Hard/soft execution limits in seconds. | 600 / 300 |
| `CELERY_DEFAULT_QUEUE` | Default Celery queue name. | `default` |

## Docker & Compose

`docker-compose.yml` already contains `celery` and `celery-beat` services. They
inherit the new environment variables automatically; no further changes are
required other than rebuilding the image so the new dependencies are available.

## Next Steps

- Place new tasks in each app's `tasks.py`. Celery will auto-discover them.
- Use the `CELERY_TASK_ALWAYS_EAGER=1` flag when writing unit tests that should
  execute synchronously.
- Add beat schedules through the Django admin once periodic jobs are ready.
