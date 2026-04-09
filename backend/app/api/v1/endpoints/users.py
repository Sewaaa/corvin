"""
User management endpoints (admin-only).

All operations are scoped to the current organization.
Admins can invite new users, list members, change roles, and deactivate accounts.
Viewers and Analysts cannot access these endpoints.
"""
import asyncio
import uuid
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org, require_admin
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.modules.notifications.service import build_invite_email_html, send_smtp_email
from app.schemas.users import (
    UserInvite,
    UserResponse,
    UserRoleUpdate,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_active_user),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    """List all users in the current organization. Accessible to all roles."""
    result = await db.execute(
        select(User)
        .where(User.organization_id == current_org.id)
        .order_by(User.created_at)
    )
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: UserInvite,
    request: Request,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Invite a new user to the organization (admin only).
    Creates the account with a temporary password and sends a branded invite email.
    """
    # Check email not already taken (across all orgs — emails are unique globally)
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    new_user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.temporary_password),
        full_name=payload.full_name,
        role=payload.role,
        organization_id=current_org.id,
        is_active=True,
        is_verified=False,
    )
    db.add(new_user)
    await db.flush()

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="user.invite",
        resource_type="user",
        resource_id=str(new_user.id),
        ip_address=request.client.host if request.client else None,
        details={"invited_role": payload.role.value},
    )

    # Send branded invite email (fire-and-forget — non-blocking)
    try:
        invite_html = build_invite_email_html(
            full_name=payload.full_name,
            org_name=current_org.name,
            email=payload.email.lower(),
            temp_password=payload.temporary_password,
            login_url=settings.frontend_url,
        )
        asyncio.create_task(
            send_smtp_email(
                to_address=payload.email.lower(),
                subject=f"Sei stato invitato su Corvin — {current_org.name}",
                body_html=invite_html,
            )
        )
    except Exception as exc:
        logger.warning("invite_email_failed", error=str(exc))

    logger.info("user_invited", org_id=str(current_org.id), role=payload.role.value)
    return UserResponse.model_validate(new_user)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Change the role of a user within the organization (admin only).
    Cannot change your own role (prevents accidental self-lockout).
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_org.id,  # tenant scope
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = target.role
    target.role = payload.role
    db.add(target)

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="user.role_change",
        resource_type="user",
        resource_id=str(target.id),
        ip_address=request.client.host if request.client else None,
        details={"old_role": old_role.value, "new_role": payload.role.value},
    )

    return UserResponse.model_validate(target)


@router.patch("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Riattiva un account precedentemente disattivato (admin only)."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_org.id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.is_active = True
    db.add(target)

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="user.reactivate",
        resource_type="user",
        resource_id=str(target.id),
        ip_address=request.client.host if request.client else None,
    )

    return UserResponse.model_validate(target)


@router.delete("/{user_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_permanent(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Elimina definitivamente un account (admin only).
    Usare solo su account disattivati — libera l'email per un nuovo invito.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_org.id,
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="user.delete_permanent",
        resource_type="user",
        resource_id=str(target.id),
        ip_address=request.client.host if request.client else None,
        details={"deleted_email": target.email},
    )

    await db.delete(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    current_org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Deactivate a user account (admin only). Does not delete — preserves audit history.
    Cannot deactivate yourself.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_org.id,  # tenant scope
        )
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target.is_active = False
    db.add(target)

    await audit(
        db,
        organization_id=current_org.id,
        user_id=current_user.id,
        action="user.deactivate",
        resource_type="user",
        resource_id=str(target.id),
        ip_address=request.client.host if request.client else None,
    )
