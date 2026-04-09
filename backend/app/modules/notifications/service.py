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


async def _send_resend_email(to_address: str, subject: str, body_html: str) -> bool:
    """Invio via Resend HTTP API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": f"{settings.email_from_name} <{settings.email_from_address or 'onboarding@resend.dev'}>",
                    "to": [to_address],
                    "subject": subject,
                    "html": body_html,
                },
            )
        if resp.status_code in (200, 201):
            logger.info("resend_delivered", to=to_address)
            return True
        logger.error("resend_failed", to=to_address, status=resp.status_code, body=resp.text[:200])
        return False
    except Exception as exc:
        logger.error("resend_error", to=to_address, error=str(exc))
        return False


async def _send_brevo_email(to_address: str, subject: str, body_html: str) -> bool:
    """Invio via Brevo (ex Sendinblue) HTTP API — non richiede dominio custom."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.brevo_api_key},
                json={
                    "sender": {
                        "name": settings.email_from_name,
                        "email": settings.email_from_address,
                    },
                    "to": [{"email": to_address}],
                    "subject": subject,
                    "htmlContent": body_html,
                },
            )
        if resp.status_code in (200, 201):
            logger.info("brevo_delivered", to=to_address)
            return True
        logger.error("brevo_failed", to=to_address, status=resp.status_code, body=resp.text[:200])
        return False
    except Exception as exc:
        logger.error("brevo_error", to=to_address, error=str(exc))
        return False


async def send_smtp_email(to_address: str, subject: str, body_html: str) -> bool:
    """Invia email: Brevo → Resend → SMTP (primo disponibile)."""
    if settings.brevo_api_key and settings.email_from_address:
        return await _send_brevo_email(to_address, subject, body_html)
    if settings.resend_api_key:
        return await _send_resend_email(to_address, subject, body_html)
    return await asyncio.to_thread(_send_smtp_sync, to_address, subject, body_html)


def build_invite_email_html(
    full_name: str,
    org_name: str,
    email: str,
    temp_password: str,
    login_url: str,
) -> str:
    """
    Email di invito branded Corvin con credenziali temporanee e link di accesso.
    Nota: SVG non supportato nei client email — si usa logo testuale.
    """
    return f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6;padding:40px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:560px;background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header violet -->
        <tr>
          <td style="background:linear-gradient(135deg,#7C3AED 0%,#6D28D9 100%);padding:36px 40px;text-align:center;">
            <img src="{settings.frontend_url}/logo-email.png" width="64" height="64" alt="Corvin" style="display:block;margin:0 auto 16px;border-radius:14px;" />
            <h1 style="margin:0;font-size:22px;font-weight:700;color:#ffffff;letter-spacing:-0.3px;">Corvin</h1>
            <p style="margin:4px 0 0;font-size:11px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:2px;">Threat Intelligence Platform</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            <h2 style="margin:0 0 8px;font-size:20px;font-weight:700;color:#111827;">Benvenuto su Corvin, {full_name}!</h2>
            <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6;">
              Sei stato invitato a unirti all'organizzazione <strong style="color:#111827;">{org_name}</strong> sulla piattaforma Corvin.<br>
              Usa le credenziali qui sotto per accedere.
            </p>

            <!-- Credentials box -->
            <div style="background:#f5f3ff;border:1px solid #ddd6fe;border-radius:12px;padding:20px 24px;margin-bottom:28px;">
              <p style="margin:0 0 4px;font-size:11px;font-weight:600;color:#7c3aed;text-transform:uppercase;letter-spacing:1px;">Le tue credenziali</p>
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;font-weight:500;width:110px;">Email</td>
                  <td style="padding:6px 0;font-size:13px;color:#111827;font-weight:600;font-family:monospace;">{email}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:13px;color:#6b7280;font-weight:500;">Password</td>
                  <td style="padding:6px 0;">
                    <span style="font-size:14px;color:#7c3aed;font-weight:700;font-family:monospace;background:#ede9fe;padding:3px 10px;border-radius:6px;">{temp_password}</span>
                  </td>
                </tr>
              </table>
            </div>

            <!-- CTA button -->
            <div style="text-align:center;margin-bottom:28px;">
              <a href="{login_url}" style="display:inline-block;background:#7C3AED;color:#ffffff;text-decoration:none;font-size:15px;font-weight:600;padding:13px 36px;border-radius:10px;letter-spacing:-0.1px;">
                Accedi a Corvin →
              </a>
            </div>

            <!-- Security note -->
            <div style="background:#fefce8;border:1px solid #fde68a;border-radius:10px;padding:14px 18px;margin-bottom:4px;">
              <p style="margin:0;font-size:13px;color:#92400e;line-height:1.5;">
                <strong>Importante:</strong> questa è una password temporanea. Ti consigliamo di cambiarla subito dopo il primo accesso nelle impostazioni del tuo profilo.
              </p>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #f3f4f6;padding:20px 40px;text-align:center;">
            <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
              Hai ricevuto questa email perché un amministratore di <strong>{org_name}</strong> ti ha invitato.<br>
              Se non ti aspettavi questo invito, puoi ignorare questa email.
            </p>
            <p style="margin:12px 0 0;font-size:11px;color:#d1d5db;">
              Corvin Security Platform &mdash; Guardiano silenzioso del tuo perimetro digitale.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


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
        Corvin Security Platform &mdash; Guardiano silenzioso del tuo perimetro digitale.
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
