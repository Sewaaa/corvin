from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationSeverity


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    severity: NotificationSeverity
    module: str
    title: str
    message: str
    recommendation: Optional[str] = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    unread: int
    page: int
    limit: int
    items: List[NotificationResponse]
