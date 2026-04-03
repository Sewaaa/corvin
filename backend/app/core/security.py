import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def _build_token(data: Dict[str, Any], expires_delta: timedelta, token_type: str) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload.update(
        {
            "iat": now,
            "exp": now + expires_delta,
            "type": token_type,
            "jti": str(uuid.uuid4()),  # unique per-token ID ensures tokens always differ
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived JWT access token (default 15 minutes)."""
    delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    return _build_token(data, delta, "access")


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a long-lived JWT refresh token."""
    delta = timedelta(days=settings.refresh_token_expire_days)
    return _build_token(data, delta, "refresh")


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        raise CREDENTIALS_EXCEPTION


def generate_totp_secret() -> str:
    """Generate a new TOTP secret using pyotp."""
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code against a secret.
    Uses a window of 1 to allow for slight clock drift.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_totp_qr_uri(secret: str, email: str) -> str:
    """Return the otpauth:// provisioning URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.mfa_issuer)


def validate_password_complexity(password: str) -> str:
    """
    Validate password complexity:
    - At least 8 characters
    - Contains uppercase, lowercase, digit, and special character
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")
    special = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
    if not any(c in special for c in password):
        raise ValueError("Password must contain at least one special character")
    return password
