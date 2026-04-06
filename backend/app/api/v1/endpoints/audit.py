"""
Audit log endpoints.

Provides read-only access to the immutable audit trail for the current
organization. Restricted to admin users.
"""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_org, require_admin
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.schemas.audit import AuditLogEntry, AuditLogListResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    action: Optional[str] = Query(None, description="Filter by action, e.g. 'user.login'"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    _admin=Depends(require_admin),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List audit log entries for the current organization, ordered by newest first."""
    logger.info(
        "audit_log.list",
        organization_id=str(current_org.id),
        page=page,
        limit=limit,
        action=action,
        user_id=str(user_id) if user_id else None,
    )

    # Base filter — always scoped to the current org
    filters = [AuditLog.organization_id == current_org.id]

    if action is not None:
        filters.append(AuditLog.action == action)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)

    # Total count for pagination metadata
    total_result = await db.execute(
        select(func.count(AuditLog.id)).where(*filters)
    )
    total = total_result.scalar_one()

    # Fetch page of entries with eager-loaded user for email
    offset = (page - 1) * limit
    rows_result = await db.execute(
        select(AuditLog)
        .where(*filters)
        .options(joinedload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = rows_result.scalars().unique().all()

    items = [
        AuditLogEntry(
            id=row.id,
            user_id=row.user_id,
            user_email=row.user.email if row.user else None,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            ip_address=row.ip_address,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return AuditLogListResponse(
        total=total,
        page=page,
        limit=limit,
        items=items,
    )
