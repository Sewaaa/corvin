import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy import Uuid as UUID

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FileStatus(str, enum.Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"


class SandboxFile(Base):
    """A file submitted for static analysis in the sandbox."""

    __tablename__ = "sandbox_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    original_filename = Column(String(512), nullable=False)
    stored_path = Column(String(1024), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(255), nullable=True)
    file_magic = Column(String(255), nullable=True)

    md5_hash = Column(String(32), nullable=True, index=True)
    sha256_hash = Column(String(64), nullable=True, index=True)

    status = Column(Enum(FileStatus), default=FileStatus.PENDING, nullable=False)

    yara_matches = Column(JSON, nullable=True)
    virustotal_result = Column(JSON, nullable=True)
    metadata_extracted = Column(JSON, nullable=True)

    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SandboxFile id={self.id} status={self.status}>"
