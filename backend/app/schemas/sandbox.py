from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.sandbox import FileStatus


class SandboxUploadResponse(BaseModel):
    """Risposta immediata dopo l'upload, prima che l'analisi completi."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_size: int
    sha256_hash: Optional[str] = None
    md5_hash: Optional[str] = None
    status: FileStatus
    created_at: datetime


class SandboxResult(BaseModel):
    """Risultato completo di analisi con tutti i campi."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_size: int
    mime_type: Optional[str] = None
    file_magic: Optional[str] = None
    sha256_hash: Optional[str] = None
    md5_hash: Optional[str] = None
    status: FileStatus
    yara_matches: Optional[List[Any]] = None
    virustotal_result: Optional[Dict[str, Any]] = None
    metadata_extracted: Optional[Dict[str, Any]] = None
    analyzed_at: Optional[datetime] = None
    created_at: datetime


class SandboxListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_size: int
    mime_type: Optional[str] = None
    sha256_hash: Optional[str] = None
    status: FileStatus
    created_at: datetime
