"""
Email Protection — API endpoints.

POST   /email/accounts            Aggiunge account IMAP (testa connessione, cifra password)
GET    /email/accounts            Lista account dell'organizzazione
GET    /email/accounts/{id}       Dettaglio account
DELETE /email/accounts/{id}       Rimuove account (admin)
POST   /email/accounts/{id}/scan  Avvia scan immediato

GET    /email/threats             Lista minacce (paginata, filtri)
GET    /email/threats/{id}        Dettaglio minaccia
PATCH  /email/threats/{id}        Azione su minaccia (quarantine/release)
"""
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin, get_current_org
from app.models.email_account import EmailAccount
from app.models.email_threat import EmailThreat
from app.models.organization import Organization
from app.models.user import User
from app.schemas.email_protection import (
    EmailAccountCreate,
    EmailAccountResponse,
    EmailActionRequest,
    EmailThreatListResponse,
    EmailThreatResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_account_or_404(account_id: UUID, org_id: UUID, db: AsyncSession) -> EmailAccount:
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.organization_id == org_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account non trovato")
    return account


async def _get_threat_or_404(threat_id: UUID, org_id: UUID, db: AsyncSession) -> EmailThreat:
    result = await db.execute(
        select(EmailThreat).where(
            EmailThreat.id == threat_id,
            EmailThreat.organization_id == org_id,
        )
    )
    threat = result.scalar_one_or_none()
    if threat is None:
        raise HTTPException(status_code=404, detail="Minaccia non trovata")
    return threat


# ---------------------------------------------------------------------------
# Account endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/accounts",
    response_model=EmailAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aggiunge un account IMAP da monitorare",
    dependencies=[Depends(require_admin)],
)
async def add_account(
    body: EmailAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    """
    Testa la connessione IMAP prima di salvare.
    La password è cifrata con Fernet — non viene mai esposta nelle risposte.
    """
    from app.modules.email_protection.service import encrypt_password, test_imap_connection

    # Verifica che lo stesso indirizzo email non sia già monitorato
    existing = await db.execute(
        select(EmailAccount).where(
            EmailAccount.organization_id == org.id,
            EmailAccount.email_address == str(body.email_address),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account già monitorato")

    # Test connessione prima di persistere
    connected = await test_imap_connection(
        host=body.imap_host,
        port=body.imap_port,
        email_addr=str(body.email_address),
        password=body.password,
        use_ssl=body.use_ssl,
    )
    if not connected:
        raise HTTPException(
            status_code=400,
            detail="Impossibile connettersi al server IMAP. Verifica host, porta e credenziali.",
        )

    encrypted = encrypt_password(body.password)
    account = EmailAccount(
        organization_id=org.id,
        email_address=str(body.email_address),
        imap_host=body.imap_host,
        imap_port=body.imap_port,
        encrypted_password=encrypted,
        use_ssl=body.use_ssl,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    logger.info("email_account_added", account_id=str(account.id), org_id=str(org.id))
    return account


@router.get(
    "/accounts",
    response_model=List[EmailAccountResponse],
    summary="Lista account email monitorati",
)
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    result = await db.execute(
        select(EmailAccount)
        .where(EmailAccount.organization_id == org.id)
        .order_by(EmailAccount.created_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/accounts/{account_id}",
    response_model=EmailAccountResponse,
    summary="Dettaglio account email",
)
async def get_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    return await _get_account_or_404(account_id, org.id, db)


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Rimuove un account email monitorato",
    dependencies=[Depends(require_admin)],
)
async def delete_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    account = await _get_account_or_404(account_id, org.id, db)
    await db.delete(account)
    await db.commit()


@router.post(
    "/accounts/{account_id}/scan",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Avvia una scansione immediata dell'account",
)
async def trigger_scan(
    account_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    account = await _get_account_or_404(account_id, org.id, db)
    if not account.is_active:
        raise HTTPException(status_code=400, detail="Account non attivo")

    from app.modules.email_protection.tasks import _scan_account_async
    background_tasks.add_task(_scan_account_async, str(account.id))

    logger.info("email_scan_triggered", account_id=str(account_id))
    return {"status": "queued", "account_id": str(account_id)}


# ---------------------------------------------------------------------------
# Threat endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/threats",
    response_model=EmailThreatListResponse,
    summary="Lista minacce email rilevate (paginata)",
)
async def list_threats(
    severity: Optional[str] = Query(None, pattern="^(critical|high|medium|low)$"),
    threat_type: Optional[str] = Query(None),
    is_quarantined: Optional[bool] = Query(None),
    recipient: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    base_query = select(EmailThreat).where(EmailThreat.organization_id == org.id)

    if severity:
        base_query = base_query.where(EmailThreat.severity == severity)
    if threat_type:
        base_query = base_query.where(EmailThreat.threat_type == threat_type)
    if is_quarantined is not None:
        base_query = base_query.where(EmailThreat.is_quarantined == is_quarantined)
    if recipient:
        base_query = base_query.where(EmailThreat.recipient == recipient)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * limit
    items_result = await db.execute(
        base_query.order_by(EmailThreat.created_at.desc()).offset(offset).limit(limit)
    )
    items = items_result.scalars().all()

    return EmailThreatListResponse(total=total, page=page, limit=limit, items=items)


@router.get(
    "/threats/{threat_id}",
    response_model=EmailThreatResponse,
    summary="Dettaglio minaccia email",
)
async def get_threat(
    threat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    return await _get_threat_or_404(threat_id, org.id, db)


@router.patch(
    "/threats/{threat_id}",
    response_model=EmailThreatResponse,
    summary="Esegui un'azione su una minaccia (quarantine / release)",
    dependencies=[Depends(require_admin)],
)
async def update_threat(
    threat_id: UUID,
    body: EmailActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    threat = await _get_threat_or_404(threat_id, org.id, db)

    if body.action == "quarantine":
        threat.is_quarantined = True
        threat.is_released = False
    elif body.action == "release":
        threat.is_released = True
        threat.is_quarantined = False

    await db.commit()
    await db.refresh(threat)
    return threat
