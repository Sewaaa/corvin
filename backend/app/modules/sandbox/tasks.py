"""
Sandbox — Celery tasks.

analyze_file_task: legge il file da disco, esegue la pipeline di analisi,
                   aggiorna lo stato nel DB.
"""
import asyncio
import os

import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="app.modules.sandbox.tasks.analyze_file_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue="sandbox",
)
def analyze_file_task(self, file_id: str) -> dict:
    """
    Carica il file dal path memorizzato ed esegue l'analisi statica completa.
    """
    try:
        return asyncio.run(_analyze_async(file_id))
    except Exception as exc:
        logger.error("sandbox_task_failed", file_id=file_id, error=str(exc))
        raise self.retry(exc=exc)


async def _analyze_async(file_id: str) -> dict:
    import uuid as _uuid
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.sandbox import SandboxFile, FileStatus
    from app.modules.sandbox.service import analyze_file

    try:
        logger.info("sandbox_bg_start", file_id=file_id)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SandboxFile).where(SandboxFile.id == _uuid.UUID(file_id))
            )
            sandbox_file = result.scalar_one_or_none()
            if sandbox_file is None:
                logger.error("sandbox_bg_not_found", file_id=file_id)
                return {"status": "not_found"}

            stored_path = sandbox_file.stored_path
            if not os.path.exists(stored_path):
                logger.error("sandbox_file_missing", file_id=file_id, path=stored_path)
                sandbox_file.status = FileStatus.SUSPICIOUS
                await db.commit()
                return {"status": "file_missing"}

            with open(stored_path, "rb") as f:
                file_data = f.read()

            await analyze_file(db, sandbox_file, file_data)
            logger.info("sandbox_bg_done", file_id=file_id, verdict=sandbox_file.status.value)
            return {"status": sandbox_file.status.value, "file_id": file_id}
    except Exception as exc:
        logger.error("sandbox_bg_failed", file_id=file_id, error=str(exc), exc_info=True)
        return {"status": "error"}
