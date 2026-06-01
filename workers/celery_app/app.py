"""
Celery application configuration.

Broker: Redis (CELERY_BROKER_URL)
Backend: Redis (CELERY_RESULT_BACKEND)
Serialization: JSON
"""

from __future__ import annotations

from celery import Celery

from shared.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_pr_reviewer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task settings
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result settings
    result_expires=3600,  # 1 hour

    # Task discovery
    task_routes={
        "workers.celery_app.tasks.review_pr": {"queue": "review"},
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["workers.celery_app"])
