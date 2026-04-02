from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# EmailAccount schemas
# ---------------------------------------------------------------------------

class EmailAccountCreate(BaseModel):
    email_address: EmailStr
    imap_host: str = Field(..., min_length=3, max_length=255)
    imap_port: int = Field(993, ge=1, le=65535)
    password: str = Field(..., min_length=1)
    use_ssl: bool = True


class EmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email_address: str
    imap_host: str
    imap_port: int
    use_ssl: bool
    is_active: bool
    last_scanned_at: Optional[datetime] = None
    last_scan_status: Optional[str] = None
    threats_count: int
    created_at: datetime


# ---------------------------------------------------------------------------
# EmailThreat schemas
# ---------------------------------------------------------------------------

class EmailThreatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_id: Optional[str] = None
    subject: Optional[str] = None
    sender: str
    recipient: str
    received_at: Optional[datetime] = None
    severity: str
    threat_type: str
    confidence_score: Optional[str] = None
    detection_reasons: List[Any] = []
    spf_result: Optional[str] = None
    dkim_result: Optional[str] = None
    dmarc_result: Optional[str] = None
    suspicious_links: Optional[List[str]] = None
    is_quarantined: bool
    is_released: bool
    created_at: datetime


class EmailThreatListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[EmailThreatResponse]


class EmailActionRequest(BaseModel):
    action: str = Field(..., pattern="^(quarantine|release)$")
