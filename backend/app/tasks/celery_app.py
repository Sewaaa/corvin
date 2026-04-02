from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "corvin",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.modules.breach_monitor.*": {"queue": "breach"},
        "app.modules.domain_reputation.*": {"queue": "domain"},
        "app.modules.web_scanner.*": {"queue": "scanner"},
        "app.modules.sandbox.*": {"queue": "sandbox"},
        "app.modules.email_protection.*": {"queue": "email"},
        "app.modules.notifications.*": {"queue": "notifications"},
    },
    beat_schedule={},
)
