"""
Domain Reputation — Celery tasks.

scan_domain: scansiona un singolo dominio (chiamato manualmente o dallo scheduler).
daily_domain_scan_all: schedulato ogni giorno, dispatcha un task per ogni dominio attivo.
"""
import asyncio
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.modules.domain_reputation.tasks.scan_domain",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    queue="domain",
)
def scan_domain(self, domain_id: str) -> dict:
    """Esegue il full scan su un dominio. Retry automatico in caso di errore."""
    try:
        return asyncio.run(_scan_domain_async(domain_id))
    except Exception as exc:
        logger.error("domain_scan_task_failed", domain_id=domain_id, error=str(exc))
        raise self.retry(exc=exc)


async def _scan_domain_async(domain_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.domain import Domain
    from app.modules.domain_reputation.service import run_domain_scan
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Domain).where(Domain.id == domain_id))
        domain_obj = result.scalar_one_or_none()

        if domain_obj is None:
            logger.warning("domain_not_found_in_task", domain_id=domain_id)
            return {"status": "not_found"}

        if not domain_obj.is_verified:
            logger.info("domain_not_verified_skip", domain=domain_obj.domain)
            return {"status": "skipped", "reason": "not_verified"}

        await run_domain_scan(db, domain_obj=domain_obj)
        await db.commit()

        return {
            "status": "completed",
            "domain": domain_obj.domain,
            "reputation_score": domain_obj.reputation_score,
        }


@celery_app.task(
    name="app.modules.domain_reputation.tasks.daily_domain_scan_all",
    queue="domain",
)
def daily_domain_scan_all() -> dict:
    """
    Schedulato da Celery Beat ogni giorno alle 03:00 UTC.
    Dispatcha un task di scan per ogni dominio verificato attivo.
    """
    return asyncio.run(_dispatch_all_domains())


async def _dispatch_all_domains() -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.domain import Domain
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Domain.id).where(Domain.is_verified == True)  # noqa: E712
        )
        domain_ids = [str(row[0]) for row in result.all()]

    for domain_id in domain_ids:
        scan_domain.delay(domain_id)

    logger.info("domain_daily_dispatch", total_domains=len(domain_ids))
    return {"dispatched": len(domain_ids)}
