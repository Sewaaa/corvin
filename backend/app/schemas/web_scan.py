from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.web_scan import ScanFrequency, ScanStatus


class ScanSchedule(BaseModel):
    domain_id: UUID
    frequency: ScanFrequency


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    severity: str
    category: str
    title: str
    description: str
    recommendation: str
    cvss_score: Optional[float] = None
    evidence: Optional[str] = None
    created_at: datetime


class ScanResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: UUID
    status: ScanStatus
    domain: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    findings: List[FindingResponse]
    summary: Dict  # {"critical": 0, "high": 1, "medium": 2, ...}
    created_at: datetime


class ScanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain_id: UUID
    status: ScanStatus
    frequency: ScanFrequency
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    finding_count: int
    created_at: datetime
