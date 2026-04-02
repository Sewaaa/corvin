from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.web_scan import ScanFrequency, ScanStatus


class ScanSchedule(BaseModel):
    domain_id: UUID
    frequency: ScanFrequency = ScanFrequency.MANUAL


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    severity: str
    category: str
    title: str
    description: str
    recommendation: Optional[str] = None
    cvss_score: Optional[float] = None
    cve_id: Optional[str] = None
    evidence: Optional[Any] = None  # JSON — dict o lista
    created_at: datetime


class ScanSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class ScanResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ScanStatus
    target_url: str
    domain_id: UUID
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    findings: List[FindingResponse] = []
    summary: ScanSummary
    created_at: datetime


class ScanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    domain_id: UUID
    target_url: str
    status: ScanStatus
    frequency: ScanFrequency
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
