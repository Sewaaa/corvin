from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.user import UserRole
from app.core.security import validate_password_complexity


class UserInvite(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.ANALYST
    temporary_password: str

    @field_validator("temporary_password")
    @classmethod
    def validate_temp_password(cls, v: str) -> str:
        return validate_password_complexity(v)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: Optional[str]
    role: UserRole
    organization_id: UUID
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    last_login: Optional[datetime] = None
    created_at: datetime
