from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl, Field

from app.models.notification import NotificationSeverity


# ---------------------------------------------------------------------------
# Notification schemas
# ---------------------------------------------------------------------------

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    severity: NotificationSeverity
    source_module: str
    source_id: Optional[str] = None
    title: str
    message: str
    is_read: bool
    is_emailed: bool
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    unread: int
    page: int
    limit: int
    items: List[NotificationResponse]


# ---------------------------------------------------------------------------
# Webhook schemas
# ---------------------------------------------------------------------------

# Tutti gli eventi supportati
SUPPORTED_EVENTS = [
    "breach.found",
    "domain.critical",
    "domain.scan_completed",
    "web_scan.completed",
    "web_scan.finding",
    "email.threat",
    "sandbox.malicious",
    "sandbox.suspicious",
]


class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    secret: Optional[str] = Field(None, min_length=8, max_length=256)
    events: List[str] = Field(default_factory=lambda: SUPPORTED_EVENTS)
    is_active: bool = True


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    # secret non esposto nelle risposte
