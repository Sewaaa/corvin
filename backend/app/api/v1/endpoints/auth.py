import re
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_qr_uri,
    hash_password,
    verify_password,
    verify_totp,
)
from app.core.audit import audit
from app.core.config import settings
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.auth import (
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

logger = structlog.get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


def _slugify(name: str) -> str:
    """Convert an organization name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100]


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Register a new user and create their organization.
    Returns access and refresh tokens on success.
    """
    # Check if email already exists — give generic message to prevent enumeration
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration failed. Please check your details and try again.",
        )

    # Create organization
    slug = _slugify(payload.organization_name)
    # Ensure slug uniqueness by appending a short UUID fragment if needed
    org_result = await db.execute(select(Organization).where(Organization.slug == slug))
    if org_result.scalar_one_or_none() is not None:
        slug = f"{slug}-{str(uuid.uuid4())[:8]}"

    org = Organization(name=payload.organization_name, slug=slug)
    db.add(org)
    await db.flush()  # Get org.id before creating user

    # Create user
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.ADMIN,  # First user in org is admin
        organization_id=org.id,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    # Audit log
    await audit(
        db,
        organization_id=org.id,
        user_id=user.id,
        action="user.register",
        ip_address=request.client.host if request.client else None,
        details={"email_domain": payload.email.split("@")[1]},
    )

    token_data = {"sub": str(user.id), "org_id": str(org.id), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user. Supports MFA via TOTP.
    Rate-limited to 5 attempts per minute per IP.
    Generic error messages prevent user enumeration.
    """
    INVALID_CREDENTIALS = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    # Always hash-compare to prevent timing attacks on non-existent accounts
    dummy_hash = hash_password("dummy-prevent-timing-attack")
    if user is None:
        verify_password(payload.password, dummy_hash)
        raise INVALID_CREDENTIALS

    if not verify_password(payload.password, user.hashed_password):
        logger.warning("login_failed", reason="bad_password")
        raise INVALID_CREDENTIALS

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    # MFA check
    if user.mfa_enabled:
        if not payload.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MFA code required",
            )
        if not verify_totp(user.mfa_secret, payload.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    await audit(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="user.login",
        ip_address=request.client.host if request.client else None,
    )

    token_data = {"sub": str(user.id), "org_id": str(user.organization_id), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access token."""
    token_payload = decode_token(payload.refresh_token)
    if token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = token_payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    token_data = {"sub": str(user.id), "org_id": str(user.organization_id), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MFASetupResponse:
    """
    Generate a new TOTP secret for the authenticated user.
    The user must verify the code before MFA is enabled.
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enabled for this account",
        )

    secret = generate_totp_secret()
    # Store secret temporarily — only activated after verify
    current_user.mfa_secret = secret
    db.add(current_user)

    qr_uri = get_totp_qr_uri(secret, current_user.email)
    return MFASetupResponse(secret=secret, qr_uri=qr_uri)


@router.post("/mfa/verify", response_model=dict)
async def verify_mfa(
    payload: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify a TOTP code and enable MFA on the account."""
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated. Call /auth/mfa/setup first.",
        )

    if not verify_totp(current_user.mfa_secret, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.mfa_enabled = True
    db.add(current_user)

    await audit(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action="user.mfa_enabled",
    )

    return {"message": "MFA enabled successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        organization_id=str(current_user.organization_id),
        is_active=current_user.is_active,
        mfa_enabled=current_user.mfa_enabled,
    )
