"""
Notifications — service layer.

Funzionalità:
- create_notification(): helper centrale chiamabile da tutti i moduli
- Deduplicazione tramite dedup_key (evita flooding per stesso evento)
- dispatch_notification(): smista su canali configurati (in-app, email, webhook)
- send_smtp_email(): invio email asincrono via smtplib + asyncio.to_thread
- send_webhook(): HTTP POST con firma HMAC-SHA256 nel header X-Corvin-Signature
- encrypt/decrypt webhook secret (Fernet, stessa chiave del modulo email)
"""
import asyncio
import base64
import hashlib
import hmac
import json
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import structlog
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import Notification, NotificationSeverity

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Encryption helpers (riusa la stessa chiave Fernet del modulo email)
# ---------------------------------------------------------------------------

def _derive_fernet_key() -> bytes:
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: str) -> str:
    return Fernet(_derive_fernet_key()).encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return Fernet(_derive_fernet_key()).decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# create_notification — entry point per tutti i moduli
# ---------------------------------------------------------------------------

async def create_notification(
    db: AsyncSession,
    *,
    organization_id: UUID,
    title: str,
    message: str,
    severity: NotificationSeverity,
    source_module: str,
    source_id: Optional[str] = None,
    user_id: Optional[UUID] = None,
    dedup_key: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Optional[Notification]:
    """
    Crea una notifica in-app con deduplicazione.
    Se dedup_key è fornito e una notifica con quella chiave esiste già
    (non letta, nelle ultime 24h), ritorna None senza crearne una nuova.
    """
    if dedup_key:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        existing = await db.execute(
            select(Notification).where(
                Notification.organization_id == organization_id,
                Notification.dedup_key == dedup_key,
                Notification.created_at >= cutoff,
            )
        )
        if existing.scalar_one_or_none():
            logger.debug("notification_deduplicated", dedup_key=dedup_key)
            return None

    notification = Notification(
        organization_id=organization_id,
        user_id=user_id,
        title=title,
        message=message,
        severity=severity,
        source_module=source_module,
        source_id=str(source_id) if source_id else None,
        dedup_key=dedup_key,
        details=details,
    )
    db.add(notification)
    await db.flush()  # ottieni l'ID senza fare commit (lascia al chiamante)

    logger.info(
        "notification_created",
        notification_id=str(notification.id),
        severity=severity,
        module=source_module,
    )
    return notification


# ---------------------------------------------------------------------------
# SMTP email
# ---------------------------------------------------------------------------

def _send_smtp_sync(to_address: str, subject: str, body_html: str) -> bool:
    """Invio sincrono via smtplib — wrappato con asyncio.to_thread."""
    if not settings.smtp_host or not settings.smtp_user:
        logger.debug("smtp_skipped", reason="not_configured")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = to_address
        msg.attach(MIMEText(body_html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_address, msg.as_string())
        return True
    except Exception as exc:
        logger.error("smtp_send_failed", to=to_address, error=str(exc))
        return False


async def send_smtp_email(to_address: str, subject: str, body_html: str) -> bool:
    """Async wrapper per invio SMTP."""
    return await asyncio.to_thread(_send_smtp_sync, to_address, subject, body_html)


def _build_email_html(notification: Notification) -> str:
    severity_colors = {
        "critical": "#dc2626",
        "high": "#ea580c",
        "medium": "#d97706",
        "low": "#2563eb",
        "info": "#6b7280",
    }
    color = severity_colors.get(notification.severity.value, "#6b7280")
    return f"""
    <html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="border-left: 4px solid {color}; padding: 16px; background: #f9fafb;">
        <h2 style="color: {color}; margin: 0 0 8px 0;">
          [{notification.severity.value.upper()}] {notification.title}
        </h2>
        <p style="color: #374151;">{notification.message}</p>
        <p style="color: #6b7280; font-size: 12px;">
          Modulo: {notification.source_module} &middot;
          {notification.created_at.strftime('%Y-%m-%d %H:%M UTC') if notification.created_at else ''}
        </p>
      </div>
      <p style="color: #9ca3af; font-size: 11px; margin-top: 16px;">
        Corvin Security Platform &mdash; Silent guardian for your digital perimeter.
      </p>
    </body></html>
    """


# ---------------------------------------------------------------------------
# Webhook dispatch con HMAC-SHA256
# ---------------------------------------------------------------------------

def _compute_hmac(payload_bytes: bytes, secret: str) -> str:
    """Calcola la firma HMAC-SHA256 del payload."""
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()


async def send_webhook(
    notification: Notification,
    webhook_url: str,
    encrypted_secret: Optional[str] = None,
) -> bool:
    """
    Invia una notifica al webhook configurato.
    Aggiunge X-Corvin-Signature: sha256=<hmac> se il secret è configurato.
    """
    payload = {
        "event": f"{notification.source_module}.alert",
        "notification_id": str(notification.id),
        "severity": notification.severity.value,
        "title": notification.title,
        "message": notification.message,
        "source_module": notification.source_module,
        "source_id": notification.source_id,
        "organization_id": str(notification.organization_id),
        "details": notification.details,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
    payload_bytes = json.dumps(payload, default=str).encode()

    req_headers = {
        "Content-Type": "application/json",
        "User-Agent": "Corvin-Security/1.0",
        "X-Corvin-Event": f"{notification.source_module}.alert",
    }

    if encrypted_secret:
        try:
            secret = decrypt_secret(encrypted_secret)
            signature = _compute_hmac(payload_bytes, secret)
            req_headers["X-Corvin-Signature"] = f"sha256={signature}"
        except Exception as exc:
            logger.warning("webhook_hmac_failed", error=str(exc))

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                webhook_url, content=payload_bytes, headers=req_headers
            )
        if 200 <= resp.status_code < 300:
            logger.info("webhook_delivered", url=webhook_url[:40], status=resp.status_code)
            return True
        logger.warning("webhook_rejected", url=webhook_url[:40], status=resp.status_code)
    except Exception as exc:
        logger.error("webhook_failed", url=webhook_url[:40], error=str(exc))
    return False


# ---------------------------------------------------------------------------
# Dispatch orchestration
# ---------------------------------------------------------------------------

async def dispatch_notification(
    db: AsyncSession,
    notification: Notification,
    *,
    email_recipients: Optional[List[str]] = None,
) -> None:
    """
    Smista la notifica su tutti i canali configurati per l'organizzazione.
    Canali: in-app (già persistita), email (se configurato), webhook.
    """
    from app.models.webhook_config import WebhookConfig

    org_id = notification.organization_id
    event_name = f"{notification.source_module}.alert"

    # ---- Webhook ----
    webhooks_result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.organization_id == org_id,
            WebhookConfig.is_active == True,  # noqa: E712
        )
    )
    webhooks = webhooks_result.scalars().all()

    for wh in webhooks:
        # Controlla se questo webhook è iscritto all'evento
        if wh.events and event_name not in wh.events and "*" not in wh.events:
            # Controlla anche pattern "breach.*", "sandbox.*"
            module_wildcard = f"{notification.source_module}.*"
            if module_wildcard not in wh.events:
                continue
        asyncio.create_task(
            send_webhook(notification, wh.url, wh.encrypted_secret)
        )

    # ---- Email ----
    if email_recipients:
        subject = f"[Corvin] [{notification.severity.value.upper()}] {notification.title}"
        html = _build_email_html(notification)
        for recipient in email_recipients:
            sent = await send_smtp_email(recipient, subject, html)
            if sent:
                notification.is_emailed = True

    await db.commit()
