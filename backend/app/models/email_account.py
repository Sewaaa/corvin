import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Uuid as UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailAccount(Base):
    """
    Account IMAP monitorato dall'organizzazione.
    La password è cifrata con Fernet prima di essere persistita.
    """

    __tablename__ = "email_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email_address = Column(String(512), nullable=False)
    imap_host = Column(String(255), nullable=False)
    imap_port = Column(Integer, default=993, nullable=False)
    encrypted_password = Column(Text, nullable=False)
    use_ssl = Column(Boolean, default=True, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    last_scanned_at = Column(DateTime(timezone=True), nullable=True)
    last_scan_status = Column(String(32), nullable=True)  # "ok" | "error" | None
    threats_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<EmailAccount id={self.id} email={self.email_address}>"
