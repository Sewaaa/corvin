"""
Web Scanner — Celery tasks.

run_web_scan_task: esegue uno scan su un singolo WebScan record.
scheduled_web_scans: controlla quali scan ricorrenti devono essere eseguiti.
"""
import asyncio
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.modules.web_scanner.tasks.run_web_scan_task",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="scanner",
)
def run_web_scan_task(self, scan_id: str) -> dict:
    """Esegue il passive scan per un WebScan già creato."""
    try:
        return asyncio.run(_run_scan_async(scan_id))
    except Exception as exc:
        logger.error("web_scan_task_failed", scan_id=scan_id, error=str(exc))
        raise self.retry(exc=exc)


async def _run_scan_async(scan_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.web_scan import WebScan, ScanStatus
    from app.modules.web_scanner.service import run_web_scan
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WebScan).where(WebScan.id == scan_id))
        scan = result.scalar_one_or_none()

        if scan is None:
            return {"status": "not_found"}

        if scan.status not in (ScanStatus.PENDING, ScanStatus.FAILED):
            return {"status": "skipped", "reason": f"scan is {scan.status}"}

        await run_web_scan(db, scan=scan)
        await db.commit()

        return {
            "status": "completed",
            "scan_id": scan_id,
            "findings": scan.findings_count,
        }


@celery_app.task(
    name="app.modules.web_scanner.tasks.scheduled_web_scans",
    queue="scanner",
)
def scheduled_web_scans() -> dict:
    """
    Schedulato ogni ora. Lancia i scan ricorrenti che sono in scadenza.
    Gestisce frequenze: daily, weekly, monthly.
    """
    return asyncio.run(_check_scheduled_scans())


async def _check_scheduled_scans() -> dict:
    from datetime import datetime, timedelta, timezone
    from app.core.database import AsyncSessionLocal
    from app.models.web_scan import WebScan, ScanStatus, ScanFrequency
    from sqlalchemy import select, or_

    now = datetime.now(timezone.utc)
    frequency_intervals = {
        ScanFrequency.DAILY: timedelta(days=1),
        ScanFrequency.WEEKLY: timedelta(weeks=1),
        ScanFrequency.MONTHLY: timedelta(days=30),
    }

    dispatched = 0
    async with AsyncSessionLocal() as db:
        for freq, interval in frequency_intervals.items():
            cutoff = now - interval
            result = await db.execute(
                select(WebScan).where(
                    WebScan.frequency == freq,
                    WebScan.status == ScanStatus.COMPLETED,
                    or_(
                        WebScan.completed_at <= cutoff,
                        WebScan.completed_at.is_(None),
                    ),
                )
            )
            scans = result.scalars().all()
            for scan in scans:
                # Crea un nuovo scan per la prossima esecuzione
                from app.modules.web_scanner.service import create_scan
                new_scan = await create_scan(
                    db,
                    organization_id=scan.organization_id,
                    domain_id=scan.domain_id,
                    target_url=scan.target_url,
                    frequency=freq,
                )
                await db.commit()
                run_web_scan_task.delay(str(new_scan.id))
                dispatched += 1

    logger.info("scheduled_scans_dispatched", count=dispatched)
    return {"dispatched": dispatched}
