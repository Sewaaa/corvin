import uuid
from datetime import datetime, date, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitoredEmail(Base):
    """
    Tracks emails being monitored for breaches.
    We NEVER store plaintext emails — only the SHA-256 hash and a masked display version.
    """

    __tablename__ = "monitored_emails"
    __table_args__ = (
        Index("ix_monitored_emails_org_hash", "organization_id", "email_hash", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SHA-256 of the lowercased email address — never the plaintext
    email_hash = Column(String(64), nullable=False, index=True)

    # Display-safe masked version: j***@example.com
    email_masked = Column(String(255), nullable=False)

    is_breached = Column(Boolean, default=False, nullable=False)
    last_checked = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    breach_records = relationship("BreachRecord", back_populates="monitored_email", lazy="select")

    def __repr__(self) -> str:
        return f"<MonitoredEmail id={self.id} masked={self.email_masked}>"


class BreachRecord(Base):
    """A single breach event associated with a monitored email."""

    __tablename__ = "breach_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitored_email_id = Column(
        UUID(as_uuid=True),
        ForeignKey("monitored_emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    breach_name = Column(String(255), nullable=False)
    breach_date = Column(Date, nullable=True)
    # List of exposed data types: ["Email", "Passwords", "Phone numbers", ...]
    data_classes = Column(JSON, nullable=False, default=list)
    description = Column(String(2048), nullable=True)

    is_notified = Column(Boolean, default=False, nullable=False)
    discovered_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    monitored_email = relationship("MonitoredEmail", back_populates="breach_records")

    def __repr__(self) -> str:
        return f"<BreachRecord id={self.id} breach={self.breach_name}>"
