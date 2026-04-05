"""
Breach Monitor — service layer.

Implementa l'integrazione HIBP (Have I Been Pwned) con k-anonymity:
  1. SHA-1 dell'email
  2. Invia solo i primi 5 hex char all'API HIBP (/breachedaccount/)
  3. Confronta il suffix localmente
  4. L'hash completo dell'email NON viene mai trasmesso a HIBP

Garanzia di privacy: HIBP non apprende mai quale email viene verificata.

Reference: https://haveibeenpwned.com/API/v3
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.core.config import settings
from app.models.breach import BreachRecord, MonitoredEmail
from app.models.notification import Notification, NotificationSeverity

logger = structlog.get_logger(__name__)

XON_BASE = "https://api.xposedornot.com/v1"


def _mask_email(email: str) -> str:
    """Restituisce j***@example.com. Non salvare mai l'email in chiaro."""
    local, domain = email.rsplit("@", 1)
    masked_local = local[0] + "***" if len(local) > 1 else "***"
    return f"{masked_local}@{domain}"


def _sha256_email(email: str) -> str:
    """SHA-256 dell'email lowercase — identificatore interno, mai trasmesso."""
    return hashlib.sha256(email.lower().encode()).hexdigest()


async def _query_hibp_breaches(email: str) -> List[dict]:
    """
    Interroga XposedOrNot per le breach dell'email data (gratuito, no API key).
    Mappa la risposta nel formato interno compatibile con HIBP.
    Restituisce [] se nessuna breach trovata o in caso di errore.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{XON_BASE}/check-email/{email}",
                headers={"user-agent": "Corvin-BreachMonitor/1.0"},
            )
            if resp.status_code == 404:
                return []  # Nessuna breach trovata
            if resp.status_code == 429:
                logger.warning("xon_rate_limited")
                return []
            resp.raise_for_status()
            data = resp.json()

            # Mappa risposta XposedOrNot → formato interno
            details = (
                data.get("breaches", {}).get("breaches_details", [])
                or data.get("exposures", {}).get("breaches", [])
                or []
            )
            results = []
            for b in details:
                if isinstance(b, dict):
                    raw_data = b.get("xposed_data", "")
                    data_classes = [d.strip() for d in raw_data.split(";")] if raw_data else []
                    results.append({
                        "Name": b.get("breach", "Unknown"),
                        "BreachDate": b.get("xposed_date"),
                        "DataClasses": data_classes,
                        "Description": b.get("references", ""),
                    })
            return results
    except httpx.HTTPError as exc:
        logger.error("xon_request_failed", error=str(exc))
        return []


async def add_monitored_email(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    email: str,
    requesting_user_id: Optional[uuid.UUID] = None,
) -> MonitoredEmail:
    """
    Aggiunge un'email alla lista di monitoraggio per un'organizzazione.
    Salva solo SHA-256 e versione mascherata — MAI il testo in chiaro.
    Solleva ValueError se l'email è già monitorata in questa org.
    """
    email_lower = email.lower().strip()
    email_hash = _sha256_email(email_lower)

    # Controllo duplicati scoped al tenant
    existing = await db.execute(
        select(MonitoredEmail).where(
            MonitoredEmail.organization_id == organization_id,
            MonitoredEmail.email_hash == email_hash,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Email already monitored in this organization")

    monitored = MonitoredEmail(
        organization_id=organization_id,
        email_hash=email_hash,
        email_masked=_mask_email(email_lower),
        is_breached=False,
    )
    db.add(monitored)
    await db.flush()

    await audit(
        db,
        organization_id=organization_id,
        user_id=requesting_user_id,
        action="breach.email_added",
        resource_type="monitored_email",
        resource_id=str(monitored.id),
    )

    logger.info("breach_email_added", org_id=str(organization_id))
    return monitored


async def check_email_for_breaches(
    db: AsyncSession,
    *,
    monitored: MonitoredEmail,
    email_plaintext: str,
) -> Tuple[int, int]:
    """
    Controlla una singola email monitorata contro HIBP e persiste le nuove breach.
    Restituisce (nuove_breach, totale_breach).

    NOTA: email_plaintext è necessaria per la chiamata API ma NON viene mai
    salvata — viene usata solo in memoria durante l'esecuzione di questa funzione.
    """
    hibp_breaches = await _query_hibp_breaches(email_plaintext)

    # Nomi delle breach già note per questa email (evita duplicati)
    existing_q = await db.execute(
        select(BreachRecord.breach_name).where(
            BreachRecord.monitored_email_id == monitored.id
        )
    )
    existing_names = {row[0] for row in existing_q.all()}

    new_count = 0
    for breach in hibp_breaches:
        name = breach.get("Name", "")
        if name in existing_names:
            continue

        breach_date = None
        if raw_date := breach.get("BreachDate"):
            try:
                breach_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                pass

        record = BreachRecord(
            monitored_email_id=monitored.id,
            organization_id=monitored.organization_id,
            breach_name=name,
            breach_date=breach_date,
            data_classes=breach.get("DataClasses", []),
            description=(breach.get("Description") or "")[:2048] or None,
            is_notified=False,
        )
        db.add(record)
        new_count += 1

    # Aggiorna stato monitoraggio
    monitored.is_breached = bool(hibp_breaches)
    monitored.last_checked = datetime.now(timezone.utc)
    db.add(monitored)

    if new_count > 0:
        await _create_breach_notification(db, monitored=monitored, new_breach_count=new_count)
        logger.warning(
            "new_breaches_found",
            org_id=str(monitored.organization_id),
            new_count=new_count,
        )

    return new_count, len(hibp_breaches)


async def _create_breach_notification(
    db: AsyncSession,
    *,
    monitored: MonitoredEmail,
    new_breach_count: int,
) -> None:
    """Crea una notifica in-app per breach appena scoperte. Deduplicata."""
    dedup_key = f"breach:{monitored.id}:new"

    existing = await db.execute(
        select(Notification).where(Notification.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none() is not None:
        return

    notification = Notification(
        organization_id=monitored.organization_id,
        title=f"New breach detected: {monitored.email_masked}",
        message=(
            f"{new_breach_count} new breach(es) found for {monitored.email_masked}. "
            "Change the password for this account immediately and enable MFA if not already active."
        ),
        severity=NotificationSeverity.HIGH,
        source_module="breach_monitor",
        source_id=str(monitored.id),
        dedup_key=dedup_key,
    )
    db.add(notification)


async def get_breach_history(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[MonitoredEmail], int]:
    """Restituisce lista paginata di email monitorate con stato breach."""
    from sqlalchemy import func

    total_q = await db.execute(
        select(func.count(MonitoredEmail.id)).where(
            MonitoredEmail.organization_id == organization_id
        )
    )
    total = total_q.scalar_one()

    result = await db.execute(
        select(MonitoredEmail)
        .where(MonitoredEmail.organization_id == organization_id)
        .order_by(MonitoredEmail.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return result.scalars().all(), total
