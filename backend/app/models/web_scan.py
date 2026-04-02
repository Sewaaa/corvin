import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


class WebScan(Base):
    """A scheduled or on-demand passive web vulnerability scan."""

    __tablename__ = "web_scans"
    __table_args__ = (
        Index("ix_web_scans_org_domain", "organization_id", "domain_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain_id = Column(
        UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_url = Column(String(2048), nullable=False)
    status = Column(Enum(ScanStatus), default=ScanStatus.PENDING, nullable=False)
    frequency = Column(Enum(ScanFrequency), default=ScanFrequency.MANUAL, nullable=False)

    findings_count = Column(Integer, default=0, nullable=False)
    critical_count = Column(Integer, default=0, nullable=False)
    high_count = Column(Integer, default=0, nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    domain = relationship("Domain", back_populates="web_scans")
    findings = relationship("ScanFinding", back_populates="scan", lazy="select")

    def __repr__(self) -> str:
        return f"<WebScan id={self.id} status={self.status}>"


class ScanFinding(Base):
    """An individual finding from a web scan."""

    __tablename__ = "scan_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("web_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    severity = Column(String(16), nullable=False, index=True)
    # Categoria finding: security_headers, exposed_files, cms, ssl, cve, info
    category = Column(String(64), nullable=False, default="info")
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)
    cvss_score = Column(Float, nullable=True)
    cve_id = Column(String(32), nullable=True)
    evidence = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    scan = relationship("WebScan", back_populates="findings")

    def __repr__(self) -> str:
        return f"<ScanFinding id={self.id} severity={self.severity}>"
