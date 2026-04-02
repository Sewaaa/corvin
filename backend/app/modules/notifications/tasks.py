"""
Notifications — Celery tasks.

dispatch_notification_task: carica la notifica dal DB e la dispatcha sui canali configurati.
"""
import asyncio
import structlog
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.modules.notifications.tasks.dispatch_notification_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="notifications",
)
def dispatch_notification_task(self, notification_id: str, email_recipients: list = None) -> dict:
    """Dispatcha una notifica già persistita su email e webhook."""
    try:
        return asyncio.run(_dispatch_async(notification_id, email_recipients or []))
    except Exception as exc:
        logger.error("dispatch_task_failed", notification_id=notification_id, error=str(exc))
        raise self.retry(exc=exc)


async def _dispatch_async(notification_id: str, email_recipients: list) -> dict:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.notification import Notification
    from app.modules.notifications.service import dispatch_notification

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            return {"status": "not_found"}
        await dispatch_notification(db, notification, email_recipients=email_recipients or None)
        return {"status": "dispatched", "notification_id": notification_id}
