"""
Email Protection — Celery tasks.

scan_email_account_task: scansiona un singolo account IMAP.
daily_email_scan_all_orgs: schedulato giornalmente, avvia scan su tutti gli account attivi.
"""
import asyncio
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.modules.email_protection.tasks.scan_email_account_task",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    queue="email",
)
def scan_email_account_task(self, account_id: str) -> dict:
    """Esegue la scansione IMAP per un singolo EmailAccount."""
    try:
        return asyncio.run(_scan_account_async(account_id))
    except Exception as exc:
        logger.error("email_scan_task_failed", account_id=account_id, error=str(exc))
        raise self.retry(exc=exc)


async def _scan_account_async(account_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.email_account import EmailAccount
    from app.modules.email_protection.service import scan_email_account
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            return {"status": "not_found"}
        if not account.is_active:
            return {"status": "skipped", "reason": "account_inactive"}

        return await scan_email_account(db, account)


@celery_app.task(
    name="app.modules.email_protection.tasks.daily_email_scan_all_orgs",
    queue="email",
)
def daily_email_scan_all_orgs() -> dict:
    """
    Schedulato giornalmente. Avvia scan su tutti gli account email attivi.
    """
    return asyncio.run(_scan_all_accounts())


async def _scan_all_accounts() -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.email_account import EmailAccount
    from sqlalchemy import select

    dispatched = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.is_active == True)  # noqa: E712
        )
        accounts = result.scalars().all()
        for account in accounts:
            scan_email_account_task.delay(str(account.id))
            dispatched += 1

    logger.info("email_scans_dispatched", count=dispatched)
    return {"dispatched": dispatched}
