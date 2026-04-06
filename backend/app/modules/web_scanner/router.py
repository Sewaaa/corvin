"""
Web Scanner — API endpoints.

POST   /web-scan/          Avvia un nuovo scan su un dominio verificato
GET    /web-scan/          Lista scan dell'organizzazione (con filtri opzionali)
GET    /web-scan/{id}      Dettaglio scan + findings
DELETE /web-scan/{id}      Elimina un scan
POST   /web-scan/schedule  Imposta frequenza ricorrente su un dominio
"""
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin, get_current_org
from app.models.organization import Organization
from app.models.user import User
from app.models.web_scan import ScanFinding, ScanStatus, ScanFrequency, WebScan
from app.schemas.web_scan import (
    ScanListItem,
    ScanResultResponse,
    ScanSchedule,
    ScanSummary,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_scan_or_404(scan_id: UUID, org_id: UUID, db: AsyncSession) -> WebScan:
    result = await db.execute(
        select(WebScan).where(
            WebScan.id == scan_id,
            WebScan.organization_id == org_id,
        )
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan non trovato")
    return scan


def _build_summary(findings: list) -> ScanSummary:
    counts: dict = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f.severity.lower()
        if sev in counts:
            counts[sev] += 1
    return ScanSummary(**counts)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ScanListItem,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Avvia un nuovo web scan",
)
async def start_scan(
    body: ScanSchedule,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    """
    Crea un WebScan record e dispatcha il task Celery.
    Il dominio deve essere verificato dall'organizzazione corrente.
    """
    from app.models.domain import Domain
    from app.modules.web_scanner.service import create_scan

    # Verifica che il dominio appartenga all'org e sia verificato
    result = await db.execute(
        select(Domain).where(
            Domain.id == body.domain_id,
            Domain.organization_id == org.id,
        )
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio non trovato")
    if not domain.is_verified:
        raise HTTPException(
            status_code=400,
            detail="Il dominio deve essere verificato prima di poter eseguire uno scan",
        )

    target_url = f"https://{domain.domain}"
    scan = await create_scan(
        db,
        organization_id=org.id,
        domain_id=domain.id,
        target_url=target_url,
        frequency=body.frequency,
    )
    await db.commit()
    await db.refresh(scan)

    from app.modules.web_scanner.tasks import _run_scan_async
    background_tasks.add_task(_run_scan_async, str(scan.id))
    logger.info("web_scan_dispatched", scan_id=str(scan.id), target=target_url)

    return scan


@router.get(
    "/",
    response_model=List[ScanListItem],
    summary="Lista scan dell'organizzazione",
)
async def list_scans(
    domain_id: Optional[UUID] = Query(None),
    status_filter: Optional[ScanStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    query = select(WebScan).where(WebScan.organization_id == org.id)
    if domain_id:
        query = query.where(WebScan.domain_id == domain_id)
    if status_filter:
        query = query.where(WebScan.status == status_filter)
    query = query.order_by(WebScan.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/{scan_id}",
    response_model=ScanResultResponse,
    summary="Dettaglio scan con findings",
)
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    scan = await _get_scan_or_404(scan_id, org.id, db)

    from app.schemas.web_scan import FindingResponse
    import uuid as _uuid

    findings_result = await db.execute(
        select(ScanFinding).where(ScanFinding.scan_id == _uuid.UUID(str(scan.id)))
    )
    findings = findings_result.scalars().all()
    summary = _build_summary(findings)

    findings_resp = [FindingResponse.model_validate(f, from_attributes=True) for f in findings]

    return ScanResultResponse(
        id=scan.id,
        status=scan.status,
        target_url=scan.target_url,
        domain_id=scan.domain_id,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        findings=findings_resp,
        summary=summary,
        created_at=scan.created_at,
    )


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un scan",
    dependencies=[Depends(require_admin)],
)
async def delete_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    scan = await _get_scan_or_404(scan_id, org.id, db)
    await db.delete(scan)
    await db.commit()


@router.post(
    "/schedule",
    response_model=ScanListItem,
    status_code=status.HTTP_200_OK,
    summary="Aggiorna frequenza ricorrente di un dominio",
    dependencies=[Depends(require_admin)],
)
async def set_schedule(
    body: ScanSchedule,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    """
    Imposta la frequenza per i futuri scan ricorrenti su un dominio.
    Crea uno scan PENDING se non ne esiste già uno in stato PENDING/RUNNING.
    """
    from app.models.domain import Domain
    from app.modules.web_scanner.service import create_scan

    result = await db.execute(
        select(Domain).where(
            Domain.id == body.domain_id,
            Domain.organization_id == org.id,
        )
    )
    domain = result.scalar_one_or_none()
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio non trovato")
    if not domain.is_verified:
        raise HTTPException(status_code=400, detail="Dominio non verificato")

    # Controlla se esiste già uno scan attivo
    existing = await db.execute(
        select(WebScan).where(
            WebScan.domain_id == domain.id,
            WebScan.organization_id == org.id,
            WebScan.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
        )
    )
    active = existing.scalar_one_or_none()
    if active:
        return active

    target_url = f"https://{domain.domain}"
    scan = await create_scan(
        db,
        organization_id=org.id,
        domain_id=domain.id,
        target_url=target_url,
        frequency=body.frequency,
    )
    await db.commit()
    await db.refresh(scan)
    return scan
