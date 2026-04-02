"""
Organization management endpoints.

All queries are scoped by organization_id from the authenticated user's JWT.
A user can only see and modify their own organization — no cross-tenant access.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org, require_admin
from app.models.notification import Notification
from app.models.organization import Organization
from app.schemas.organization import OrgSummary, OrganizationResponse

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=OrganizationResponse)
async def get_my_organization(
    current_org: Organization = Depends(get_current_org),
) -> OrganizationResponse:
    """Return the authenticated user's organization."""
    return OrganizationResponse.model_validate(current_org)


@router.get("/summary", response_model=OrgSummary)
async def get_org_summary(
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> OrgSummary:
    """
    Return a high-level risk summary for the organization dashboard.
    Counts active unread alerts and computes a simple risk score.
    """
    from app.models.notification import NotificationSeverity

    # Count unread alerts per severity — all scoped to this org
    unread_q = await db.execute(
        select(
            Notification.severity,
            func.count(Notification.id).label("cnt"),
        )
        .where(
            Notification.organization_id == current_org.id,
            Notification.is_read == False,  # noqa: E712
        )
        .group_by(Notification.severity)
    )
    severity_counts = {row.severity: row.cnt for row in unread_q}

    active_alerts = sum(severity_counts.values())

    # Simple risk score: critical=40pts, high=20pts, medium=10pts, low=5pts
    risk_score = min(
        100,
        severity_counts.get(NotificationSeverity.CRITICAL, 0) * 40
        + severity_counts.get(NotificationSeverity.HIGH, 0) * 20
        + severity_counts.get(NotificationSeverity.MEDIUM, 0) * 10
        + severity_counts.get(NotificationSeverity.LOW, 0) * 5,
    )

    return OrgSummary(
        org=OrganizationResponse.model_validate(current_org),
        total_threats=active_alerts,
        active_alerts=active_alerts,
        modules_enabled=["breach_monitor", "domain_reputation"],  # TODO: dynamic per org config
        risk_score=risk_score,
    )
