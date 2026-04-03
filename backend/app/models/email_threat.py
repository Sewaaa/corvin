import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String
from sqlalchemy import Uuid as UUID

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailThreat(Base):
    """A flagged email threat detected by the email protection module."""

    __tablename__ = "email_threats"

    id = Column(UUID(as_uuid=True, native_uuid=False), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True, native_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    message_id = Column(String(512), nullable=True)
    subject = Column(String(1024), nullable=True)
    sender = Column(String(512), nullable=False)
    recipient = Column(String(512), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True)

    severity = Column(String(16), nullable=False, index=True)
    threat_type = Column(String(64), nullable=False)
    confidence_score = Column(String(16), nullable=True)

    detection_reasons = Column(JSON, nullable=False, default=list)
    spf_result = Column(String(16), nullable=True)
    dkim_result = Column(String(16), nullable=True)
    dmarc_result = Column(String(16), nullable=True)
    suspicious_links = Column(JSON, nullable=True)
    attachment_hashes = Column(JSON, nullable=True)

    is_quarantined = Column(Boolean, default=False, nullable=False)
    is_released = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<EmailThreat id={self.id} type={self.threat_type} severity={self.severity}>"
