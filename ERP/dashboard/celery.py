"""Celery application bootstrap for the Himalytix dashboard project."""
from __future__ import annotations

import os

import structlog
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard.settings")

logger = structlog.get_logger(__name__)

app = Celery("dashboard")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def heartbeat(self):
	"""Trivial task to verify the worker is responsive."""
	logger.info("celery.heartbeat", task_id=self.request.id)
	return {"ok": True}
