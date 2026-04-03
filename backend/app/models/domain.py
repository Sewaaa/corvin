import uuid
from datetime import datetime, date, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Domain(Base):
    """A domain being monitored for reputation, DNS health, and SSL status."""

    __tablename__ = "domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain = Column(String(255), nullable=False, index=True)

    # Domain ownership verification via DNS TXT record
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(64), nullable=True)

    # Monitoring data
    dns_check_at = Column(DateTime(timezone=True), nullable=True)
    ssl_expiry = Column(Date, nullable=True)

    # Reputation: 0 (terrible) - 100 (clean)
    reputation_score = Column(Integer, nullable=True)
    is_blacklisted = Column(Boolean, default=False, nullable=False)

    # Risultati dell'ultimo scan (JSON — aggiornato ad ogni check)
    dns_records = Column(JSON, nullable=True)      # MX, SPF, DMARC, NS records
    scan_findings = Column(JSON, nullable=True)    # Lista di finding con severity
    whois_data = Column(JSON, nullable=True)       # Dati WHOIS rilevanti

    last_scan_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="domains")
    web_scans = relationship("WebScan", back_populates="domain", lazy="select")

    def __repr__(self) -> str:
        return f"<Domain id={self.id} domain={self.domain}>"
