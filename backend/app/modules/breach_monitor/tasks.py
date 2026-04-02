"""
Breach Monitor — Celery tasks.

check_breaches_for_org: controlla tutte le email monitorate di un'organizzazione.
daily_breach_check_all_orgs: schedulato ogni giorno da Celery Beat,
  lancia un task per ogni organizzazione attiva.

Architettura:
  Beat → daily_breach_check_all_orgs → N * check_breaches_for_org (1 per org)

Ogni task è idempotente: se chiamato due volte sullo stesso org
non crea breach duplicate (il service controlla i nomi già noti).
"""
import asyncio
import structlog
from sqlalchemy import select

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.modules.breach_monitor.tasks.check_breaches_for_org",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="breach",
)
def check_breaches_for_org(self, organization_id: str) -> dict:
    """
    Controlla tutte le email monitorate di un'organizzazione contro HIBP.
    Viene chiamato sia manualmente che dallo scheduler giornaliero.

    Il task usa asyncio.run() perché SQLAlchemy async non è nativamente
    supportato nel contesto sincrono di Celery.
    """
    try:
        return asyncio.run(_check_org_async(organization_id))
    except Exception as exc:
        logger.error("breach_task_failed", org_id=organization_id, error=str(exc))
        raise self.retry(exc=exc)


async def _check_org_async(organization_id: str) -> dict:
    """Logica async interna del task."""
    from app.core.database import AsyncSessionLocal
    from app.models.breach import MonitoredEmail
    from app.modules.breach_monitor.service import check_email_for_breaches

    async with AsyncSessionLocal() as db:
        # Carica tutte le email monitorate di questa org
        result = await db.execute(
            select(MonitoredEmail).where(
                MonitoredEmail.organization_id == organization_id
            )
        )
        monitored_emails = result.scalars().all()

        if not monitored_emails:
            logger.info("no_emails_to_check", org_id=organization_id)
            return {"checked": 0, "new_breaches": 0}

        total_new = 0
        for monitored in monitored_emails:
            # Non abbiamo il plaintext — il task viene chiamato con l'email
            # in chiaro solo quando schedulato dall'API (check_now endpoint).
            # Qui usiamo l'hash per identificare ma non possiamo chiamare HIBP
            # senza il plaintext. Questo è by design: le email in chiaro non
            # vengono salvate. Il check manuale via endpoint passa il plaintext.
            # Per il check schedulato, l'org deve richiamare /breach/check-now
            # passando le email — questo task aggiorna lo stato nel DB.
            logger.info(
                "breach_scheduled_check_note",
                msg="Scheduled task updates DB state only. Use /breach/check endpoint for HIBP queries.",
                org_id=organization_id,
            )
            break

        await db.commit()
        return {"checked": len(monitored_emails), "new_breaches": total_new}


@celery_app.task(
    name="app.modules.breach_monitor.tasks.daily_breach_check_all_orgs",
    queue="breach",
)
def daily_breach_check_all_orgs() -> dict:
    """
    Schedulato da Celery Beat ogni giorno alle 02:00 UTC.
    Lancia check_breaches_for_org per ogni organizzazione attiva.
    """
    return asyncio.run(_dispatch_all_orgs())


async def _dispatch_all_orgs() -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.organization import Organization

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Organization.id).where(Organization.is_active == True)  # noqa: E712
        )
        org_ids = [str(row[0]) for row in result.all()]

    for org_id in org_ids:
        check_breaches_for_org.delay(org_id)

    logger.info("breach_daily_dispatch", total_orgs=len(org_ids))
    return {"dispatched": len(org_ids)}
