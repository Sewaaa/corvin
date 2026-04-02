"""
Reusable audit log helper.

All security-relevant actions across every module must be logged here.
The audit_logs table is append-only — never update or delete rows.

Usage:
    await audit(db, org_id=org.id, action="breach.check", user_id=user.id)
"""
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def audit(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a single audit log entry.

    Action naming convention: "<module>.<verb>"
    Examples: "user.login", "breach.check", "domain.add", "scan.create"

    Rules:
    - Never include plaintext passwords, tokens, or full email addresses in details.
    - Always call this for auth events, data creation, and security-relevant changes.
    """
    entry = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(entry)
    # Note: caller is responsible for commit (session is managed by get_db dependency)
