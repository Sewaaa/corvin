from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EmailThreatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sender: str
    severity: str
    threat_types: List[str]
    spf_result: Optional[str] = None
    dkim_result: Optional[str] = None
    dmarc_result: Optional[str] = None
    is_quarantined: bool
    action_taken: Optional[str] = None
    received_at: datetime
    created_at: datetime


class EmailThreatListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[EmailThreatResponse]


class EmailActionRequest(BaseModel):
    action: str  # "quarantine", "release", "delete"

    model_config = {"from_attributes": True}
