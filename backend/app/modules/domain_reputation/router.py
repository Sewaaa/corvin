"""
Domain Reputation — API router.

Endpoint:
  POST /domain/           — aggiungi dominio (genera token di verifica)
  GET  /domain/           — lista domini dell'org
  GET  /domain/{id}       — dettaglio dominio con ultimo report
  POST /domain/{id}/verify — verifica ownership via DNS TXT
  POST /domain/{id}/scan  — avvia scan immediato (solo domini verificati)
  DELETE /domain/{id}     — rimuovi dominio
"""
import uuid
from typing import List

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org, require_analyst
from app.models.domain import Domain
from app.models.organization import Organization
from app.models.user import User
from app.modules.domain_reputation.service import (
    add_domain,
    run_domain_scan,
    verify_domain_ownership,
)
from app.schemas.domain import (
    DomainAdd,
    DomainReport,
    DomainResponse,
    DomainVerifyResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=DomainVerifyResponse, status_code=status.HTTP_201_CREATED)
async def add_domain_endpoint(
    payload: DomainAdd,
    request: Request,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> DomainVerifyResponse:
    """
    Aggiunge un dominio all'organizzazione.
    Restituisce il token TXT da aggiungere al DNS per verificarne il possesso.
    Il dominio non viene scansionato finché non è verificato.
    """
    try:
        domain_obj = await add_domain(
            db,
            organization_id=current_org.id,
            domain_name=payload.domain,
            requesting_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return DomainVerifyResponse(
        domain=domain_obj.domain,
        verification_token=domain_obj.verification_token,
        instructions=(
            f"Add a DNS TXT record to {domain_obj.domain} with value: "
            f"{domain_obj.verification_token} — then call POST /domain/{domain_obj.id}/verify"
        ),
    )


@router.get("/", response_model=List[DomainResponse])
async def list_domains(
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> List[DomainResponse]:
    """Lista domini dell'organizzazione (tenant-scoped)."""
    result = await db.execute(
        select(Domain)
        .where(Domain.organization_id == current_org.id)
        .order_by(Domain.created_at.desc())
    )
    domains = result.scalars().all()
    return [DomainResponse.model_validate(d) for d in domains]


@router.get("/{domain_id}", response_model=DomainReport)
async def get_domain_report(
    domain_id: uuid.UUID,
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> DomainReport:
    """Restituisce il report dettagliato dell'ultimo scan per un dominio."""
    domain_obj = await _get_domain_or_404(db, domain_id, current_org.id)

    dns_records = domain_obj.dns_records or {}
    findings = domain_obj.scan_findings or []

    # Calcola giorni rimanenti SSL
    ssl_days = None
    if domain_obj.ssl_expiry:
        from datetime import date
        ssl_days = (domain_obj.ssl_expiry - date.today()).days

    # Estrai dati DMARC/SPF dai record DNS
    dmarc_list = dns_records.get("dmarc", [])
    spf_list = dns_records.get("spf", [])

    return DomainReport(
        domain=domain_obj.domain,
        is_verified=domain_obj.is_verified,
        reputation_score=domain_obj.reputation_score,
        is_blacklisted=domain_obj.is_blacklisted,
        ssl_expiry=domain_obj.ssl_expiry,
        ssl_days_remaining=ssl_days,
        dns_records=dns_records,
        dmarc_policy=dmarc_list[0] if dmarc_list else None,
        spf_record=spf_list[0] if spf_list else None,
        findings=[f.get("title", "") for f in findings],
        last_scan_at=domain_obj.last_scan_at,
    )


@router.post("/{domain_id}/verify", response_model=DomainResponse)
async def verify_domain(
    domain_id: uuid.UUID,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> DomainResponse:
    """
    Verifica l'ownership del dominio controllando il record DNS TXT.
    Deve essere chiamato dopo aver aggiunto il record TXT al DNS.
    """
    domain_obj = await _get_domain_or_404(db, domain_id, current_org.id)

    if domain_obj.is_verified:
        return DomainResponse.model_validate(domain_obj)

    verified = await verify_domain_ownership(db, domain_obj=domain_obj)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Verification failed. Ensure the DNS TXT record "
                f"'{domain_obj.verification_token}' is present for {domain_obj.domain}. "
                "DNS propagation can take up to 48 hours."
            ),
        )

    domain_obj.is_verified = True
    db.add(domain_obj)
    await db.commit()
    await db.refresh(domain_obj)

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="domain.verified",
        resource_type="domain",
        resource_id=str(domain_obj.id),
    )

    return DomainResponse.model_validate(domain_obj)


@router.post("/{domain_id}/scan", response_model=DomainResponse)
async def scan_domain_now(
    domain_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> DomainResponse:
    """
    Avvia un full scan passivo immediato sul dominio.
    Richiede che il dominio sia verificato (ownership check).
    Il scan viene eseguito in background — l'endpoint risponde subito con 200.
    """
    domain_obj = await _get_domain_or_404(db, domain_id, current_org.id)

    if not domain_obj.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before scanning. Call POST /domain/{id}/verify first.",
        )

    # Usa BackgroundTasks di FastAPI per scan leggeri in-process
    # Per scan pesanti usa il task Celery: scan_domain.delay(str(domain_id))
    background_tasks.add_task(
        _run_scan_background, str(domain_id), str(current_user.id)
    )

    return DomainResponse.model_validate(domain_obj)


async def _run_scan_background(domain_id: str, user_id: str) -> None:
    """Esegue il scan in background con una sessione DB indipendente."""
    import uuid as _uuid
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select

    try:
        logger.info("domain_scan_bg_start", domain_id=domain_id)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Domain).where(Domain.id == _uuid.UUID(domain_id))
            )
            domain_obj = result.scalar_one_or_none()
            if domain_obj is None:
                logger.error("domain_scan_bg_not_found", domain_id=domain_id)
                return
            logger.info("domain_scan_bg_running", domain=domain_obj.domain)
            await run_domain_scan(
                db, domain_obj=domain_obj,
                requesting_user_id=_uuid.UUID(user_id),
            )
            await db.commit()
            logger.info("domain_scan_bg_done", domain=domain_obj.domain,
                        score=domain_obj.reputation_score)
    except Exception as exc:
        logger.error("domain_scan_bg_failed", domain_id=domain_id, error=str(exc),
                     exc_info=True)


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_domain(
    domain_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Rimuove un dominio e tutti i suoi scan (tenant-scoped)."""
    domain_obj = await _get_domain_or_404(db, domain_id, current_org.id)
    await db.delete(domain_obj)

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="domain.remove",
        resource_type="domain",
        resource_id=str(domain_id),
    )


async def _get_domain_or_404(
    db: AsyncSession, domain_id: uuid.UUID, organization_id: uuid.UUID
) -> Domain:
    """Helper: carica un dominio scoped al tenant, altrimenti 404."""
    result = await db.execute(
        select(Domain).where(
            Domain.id == domain_id,
            Domain.organization_id == organization_id,  # tenant scope
        )
    )
    domain_obj = result.scalar_one_or_none()
    if domain_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    return domain_obj
