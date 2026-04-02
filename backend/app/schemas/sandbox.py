from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.sandbox import FileStatus


class SandboxResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: UUID
    original_filename: str
    file_size: int
    mime_type: str
    sha256_hash: str
    status: FileStatus
    yara_matches: List[str]
    vt_detections: Optional[int] = None
    vt_total: Optional[int] = None
    metadata: Optional[Dict] = None
    analyzed_at: Optional[datetime] = None
    uploaded_at: datetime


class SandboxListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_size: int
    mime_type: str
    status: FileStatus
    sha256_hash: str
    uploaded_at: datetime
