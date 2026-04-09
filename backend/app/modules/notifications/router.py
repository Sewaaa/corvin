"""
Notifications — API endpoints.

GET    /notifications/               Lista notifiche (paginata, filtri)
GET    /notifications/{id}           Dettaglio notifica
PATCH  /notifications/{id}/read      Segna come letta
POST   /notifications/read-all       Segna tutte come lette

GET    /notifications/webhooks       Lista webhook configurati
POST   /notifications/webhooks       Aggiunge webhook
DELETE /notifications/webhooks/{id}  Rimuove webhook
POST   /notifications/webhooks/{id}/test  Invia notifica di test
"""
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_admin, get_current_org
from app.models.notification import Notification, NotificationSeverity
from app.models.organization import Organization
from app.models.user import User
from app.models.webhook_config import WebhookConfig
from app.modules.notifications.service import send_webhook  # needed for test patching
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    WebhookCreate,
    WebhookResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_notification_or_404(notif_id: UUID, org_id: UUID, db: AsyncSession) -> Notification:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.organization_id == org_id,
        )
    )
    n = result.scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Notifica non trovata")
    return n


async def _get_webhook_or_404(webhook_id: UUID, org_id: UUID, db: AsyncSession) -> WebhookConfig:
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == webhook_id,
            WebhookConfig.organization_id == org_id,
        )
    )
    wh = result.scalar_one_or_none()
    if wh is None:
        raise HTTPException(status_code=404, detail="Webhook non trovato")
    return wh


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Webhook endpoints (must be registered BEFORE /{notification_id} to avoid
# FastAPI matching "/webhooks" as a UUID path parameter)
# ---------------------------------------------------------------------------

@router.get(
    "/webhooks",
    response_model=List[WebhookResponse],
    summary="Lista webhook configurati",
    dependencies=[Depends(require_admin)],
)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    result = await db.execute(
        select(WebhookConfig)
        .where(WebhookConfig.organization_id == org.id)
        .order_by(WebhookConfig.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aggiunge un webhook",
    dependencies=[Depends(require_admin)],
)
async def add_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    from app.modules.notifications.service import encrypt_secret

    encrypted = encrypt_secret(body.secret) if body.secret else None
    wh = WebhookConfig(
        organization_id=org.id,
        url=body.url,
        encrypted_secret=encrypted,
        events=body.events,
        is_active=body.is_active,
    )
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    logger.info("webhook_added", webhook_id=str(wh.id), org_id=str(org.id))
    return wh


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Rimuove un webhook",
    dependencies=[Depends(require_admin)],
)
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    wh = await _get_webhook_or_404(webhook_id, org.id, db)
    await db.delete(wh)
    await db.commit()


@router.post(
    "/webhooks/{webhook_id}/test",
    status_code=status.HTTP_200_OK,
    summary="Invia una notifica di test al webhook",
    dependencies=[Depends(require_admin)],
)
async def test_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    from app.models.notification import NotificationSeverity

    wh = await _get_webhook_or_404(webhook_id, org.id, db)

    test_notif = Notification(
        organization_id=org.id,
        title="Corvin Webhook Test",
        message="Questa è una notifica di test dal sistema Corvin.",
        severity=NotificationSeverity.INFO,
        source_module="system",
        source_id="webhook_test",
    )
    from datetime import datetime, timezone
    test_notif.created_at = datetime.now(timezone.utc)

    delivered = await send_webhook(test_notif, wh.url, wh.encrypted_secret)
    return {
        "delivered": delivered,
        "webhook_id": str(webhook_id),
        "url": wh.url,
    }


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=NotificationListResponse,
    summary="Lista notifiche dell'organizzazione",
)
async def list_notifications(
    severity: Optional[NotificationSeverity] = Query(None),
    source_module: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    base = select(Notification).where(Notification.organization_id == org.id)
    if severity:
        base = base.where(Notification.severity == severity)
    if source_module:
        base = base.where(Notification.source_module == source_module)
    if is_read is not None:
        base = base.where(Notification.is_read == is_read)

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    unread_result = await db.execute(
        select(func.count()).select_from(
            select(Notification).where(
                Notification.organization_id == org.id,
                Notification.is_read == False,  # noqa: E712
            ).subquery()
        )
    )
    unread = unread_result.scalar_one()

    offset = (page - 1) * limit
    items_result = await db.execute(
        base.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    )
    items = items_result.scalars().all()

    return NotificationListResponse(total=total, unread=unread, page=page, limit=limit, items=items)


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Dettaglio notifica",
)
async def get_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    return await _get_notification_or_404(notification_id, org.id, db)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Segna una notifica come letta",
)
async def mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    notification = await _get_notification_or_404(notification_id, org.id, db)
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post(
    "/read-all",
    status_code=status.HTTP_200_OK,
    summary="Segna tutte le notifiche come lette",
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org: Organization = Depends(get_current_org),
):
    await db.execute(
        update(Notification)
        .where(
            Notification.organization_id == org.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "ok", "message": "Tutte le notifiche sono state segnate come lette"}


@router.delete(
    "/all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina tutte le notifiche dell'organizzazione (solo admin)",
    dependencies=[Depends(require_admin)],
)
async def delete_all_notifications(
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_current_org),
):
    await db.execute(delete(Notification).where(Notification.organization_id == org.id))
    await db.commit()


