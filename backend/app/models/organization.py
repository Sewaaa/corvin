import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True, native_uuid=False), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Hashed API key for programmatic access (nullable — feature flag)
    api_key_hash = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", lazy="select")
    domains = relationship("Domain", back_populates="organization", lazy="select")
    audit_logs = relationship("AuditLog", back_populates="organization", lazy="select")

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug}>"
