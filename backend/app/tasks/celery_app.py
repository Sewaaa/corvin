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
    beat_schedule={
        # Breach check giornaliero alle 02:00 UTC
        "daily-breach-check": {
            "task": "app.modules.breach_monitor.tasks.daily_breach_check_all_orgs",
            "schedule": 86400,
            "options": {"queue": "breach"},
        },
        # Domain scan giornaliero alle 03:00 UTC
        "daily-domain-scan": {
            "task": "app.modules.domain_reputation.tasks.daily_domain_scan_all",
            "schedule": 86400,
            "options": {"queue": "domain"},
        },
    },
)
