from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class EmailAddRequest(BaseModel):
    emails: List[EmailStr]

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v: List[EmailStr]) -> List[EmailStr]:
        if len(v) == 0:
            raise ValueError("At least one email address is required")
        if len(v) > 100:
            raise ValueError("Maximum 100 email addresses per request")
        return v


class BreachDetail(BaseModel):
    breach_name: str
    breach_date: Optional[date] = None
    data_classes: List[str]
    description: Optional[str] = None


class BreachCheckResponse(BaseModel):
    email_masked: str
    is_breached: bool
    breach_count: int
    breaches: List[BreachDetail]


class MonitoredEmailResponse(BaseModel):
    id: UUID
    email_masked: str
    is_breached: bool
    breach_count: int = 0
    breach_names: List[str] = []
    last_checked: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BreachHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BreachCheckResponse]
