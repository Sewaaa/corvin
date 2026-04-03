import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy import Uuid as UUID

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WebhookConfig(Base):
    """
    Configurazione webhook per un'organizzazione.
    Il secret è cifrato con Fernet per firma HMAC-SHA256 dei payload.
    """

    __tablename__ = "webhook_configs"

    id = Column(UUID(as_uuid=True, native_uuid=False), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True, native_uuid=False),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    url = Column(String(2048), nullable=False)
    encrypted_secret = Column(Text, nullable=True)   # HMAC signing secret (Fernet)
    events = Column(JSON, nullable=False, default=list)  # ["breach.found", "sandbox.malicious", ...]
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<WebhookConfig id={self.id} url={self.url[:40]}>"
