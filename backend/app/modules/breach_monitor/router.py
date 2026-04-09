"""
Breach Monitor — API router.

Endpoint:
  POST /breach/emails          — aggiungi email al monitoraggio
  GET  /breach/emails          — lista email monitorate (paginata)
  POST /breach/check           — controlla subito le email via HIBP
  GET  /breach/history         — cronologia breach per l'org
  DELETE /breach/emails/{id}   — rimuovi email dal monitoraggio
"""
import uuid
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org, require_analyst
from app.models.breach import BreachRecord, MonitoredEmail
from app.models.organization import Organization
from app.models.user import User
from app.modules.breach_monitor.service import (
    add_monitored_email,
    check_email_for_breaches,
    get_breach_history,
)
from app.schemas.breach import (
    BreachCheckResponse,
    BreachDetail,
    BreachHistoryResponse,
    EmailAddRequest,
    MonitoredEmailResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/emails",
    response_model=List[MonitoredEmailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_emails(
    payload: EmailAddRequest,
    request: Request,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> List[MonitoredEmailResponse]:
    """
    Aggiunge una o più email al monitoraggio breach dell'organizzazione.
    Le email vengono salvate come SHA-256 hash — mai in chiaro.
    """
    added = []
    skipped = []

    for email in payload.emails:
        try:
            monitored = await add_monitored_email(
                db,
                organization_id=current_org.id,
                email=str(email),
                requesting_user_id=current_user.id,
            )
            added.append(monitored)
        except ValueError:
            skipped.append(str(email))

    if skipped:
        logger.info("breach_emails_skipped_duplicates", count=len(skipped))

    await db.commit()

    return [MonitoredEmailResponse.model_validate(m) for m in added]


@router.get("/emails", response_model=List[MonitoredEmailResponse])
async def list_monitored_emails(
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    limit: int = 50,
) -> List[MonitoredEmailResponse]:
    """Lista di email monitorate per questa organizzazione (tenant-scoped)."""
    from sqlalchemy import func
    if limit > 100:
        limit = 100

    emails, _total = await get_breach_history(
        db, organization_id=current_org.id, page=page, limit=limit
    )

    # Count and fetch breach names per email
    results = []
    for e in emails:
        records_q = await db.execute(
            select(BreachRecord.breach_name).where(
                BreachRecord.monitored_email_id == e.id
            )
        )
        names = [row[0] for row in records_q.all()]
        item = MonitoredEmailResponse.model_validate(e)
        item.breach_count = len(names)
        item.breach_names = names
        results.append(item)
    return results


@router.post("/check", response_model=List[BreachCheckResponse])
async def check_breaches_now(
    payload: EmailAddRequest,
    request: Request,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> List[BreachCheckResponse]:
    """
    Controlla immediatamente una lista di email contro HIBP.

    Questo è l'unico endpoint che riceve email in chiaro —
    necessario per la chiamata HIBP. Le email NON vengono salvate in chiaro;
    vengono usate solo per la query e poi scartate.

    Se un'email non è ancora monitorata, viene aggiunta automaticamente.
    """
    results = []

    for email in payload.emails:
        email_str = str(email)

        # Aggiungi al monitoraggio se non presente (ignora duplicati)
        try:
            await add_monitored_email(
                db,
                organization_id=current_org.id,
                email=email_str,
                requesting_user_id=current_user.id,
            )
        except ValueError:
            pass  # Già monitorata

        # Carica il record monitorato (per id e stato)
        from app.modules.breach_monitor.service import _sha256_email
        email_hash = _sha256_email(email_str)
        result = await db.execute(
            select(MonitoredEmail).where(
                MonitoredEmail.organization_id == current_org.id,
                MonitoredEmail.email_hash == email_hash,
            )
        )
        monitored = result.scalar_one_or_none()
        if monitored is None:
            continue

        # Controlla HIBP (email_plaintext usata solo qui, mai salvata)
        new_count, total_count = await check_email_for_breaches(
            db, monitored=monitored, email_plaintext=email_str
        )

        # Carica le breach per la risposta
        breach_q = await db.execute(
            select(BreachRecord).where(BreachRecord.monitored_email_id == monitored.id)
        )
        breaches = breach_q.scalars().all()

        results.append(
            BreachCheckResponse(
                email_masked=monitored.email_masked,
                is_breached=monitored.is_breached,
                breach_count=len(breaches),
                breaches=[
                    BreachDetail(
                        breach_name=b.breach_name,
                        breach_date=b.breach_date,
                        data_classes=b.data_classes,
                        description=b.description,
                    )
                    for b in breaches
                ],
            )
        )

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="breach.check",
        ip_address=request.client.host if request.client else None,
        details={"email_count": len(payload.emails)},
    )

    await db.commit()

    return results


@router.get("/history", response_model=BreachHistoryResponse)
async def get_history(
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    limit: int = 20,
) -> BreachHistoryResponse:
    """Cronologia paginata delle breach rilevate per questa organizzazione."""
    if limit > 100:
        limit = 100

    emails, total = await get_breach_history(
        db, organization_id=current_org.id, page=page, limit=limit
    )

    items = []
    for monitored in emails:
        breach_q = await db.execute(
            select(BreachRecord).where(BreachRecord.monitored_email_id == monitored.id)
        )
        breaches = breach_q.scalars().all()
        items.append(
            BreachCheckResponse(
                email_masked=monitored.email_masked,
                is_breached=monitored.is_breached,
                breach_count=len(breaches),
                breaches=[
                    BreachDetail(
                        breach_name=b.breach_name,
                        breach_date=b.breach_date,
                        data_classes=b.data_classes,
                        description=b.description,
                    )
                    for b in breaches
                ],
            )
        )

    return BreachHistoryResponse(total=total, page=page, limit=limit, items=items)


@router.delete("/emails/{monitored_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_monitored_email(
    monitored_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_analyst),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Rimuove un'email dal monitoraggio (tenant-scoped — non può rimuovere email di altre org)."""
    result = await db.execute(
        select(MonitoredEmail).where(
            MonitoredEmail.id == monitored_id,
            MonitoredEmail.organization_id == current_org.id,  # tenant scope
        )
    )
    monitored = result.scalar_one_or_none()
    if monitored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    # Elimina prima i BreachRecord correlati (evita lazy-load in async)
    await db.execute(
        delete(BreachRecord).where(BreachRecord.monitored_email_id == monitored.id)
    )
    await db.delete(monitored)

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="breach.email_removed",
        resource_type="monitored_email",
        resource_id=str(monitored_id),
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
