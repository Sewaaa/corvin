"""
Email Protection — service layer.

Funzionalità:
- Cifratura/decifratura password IMAP con Fernet (chiave derivata da secret_key)
- Test connessione IMAP
- Fetch email recenti via IMAP (passivo: sola lettura)
- Pipeline di analisi phishing:
    1. Auth header parsing (SPF/DKIM/DMARC)
    2. From/Reply-To mismatch
    3. Display-name spoofing
    4. Lookalike domain (distanza di Levenshtein)
    5. Urgency keyword detection
    6. Suspicious link extraction
- Calcolo severity + confidence
- Persistenza EmailThreat
"""
import asyncio
import base64
import email
import hashlib
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import structlog
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

# Keyword di urgenza / pressione sociale tipiche del phishing
URGENCY_KEYWORDS = [
    "urgent", "immediate action", "account suspended", "verify your account",
    "click here now", "act now", "limited time", "your account has been",
    "confirm your identity", "unusual activity", "login attempt",
    "password expired", "security alert", "update your payment",
    "invoice attached", "wire transfer", "kindly", "reconfirm",
]

# Schemi URL legittimi da escludere dall'analisi link
TRUSTED_LINK_PATTERNS = [
    r"https?://unsubscribe\.",
    r"https?://[^/]+/unsubscribe",
]

# Domini di organizzazioni comuni che vengono impersonati
HIGH_VALUE_TARGETS = [
    "paypal", "amazon", "google", "microsoft", "apple", "facebook",
    "instagram", "linkedin", "twitter", "netflix", "dropbox", "github",
    "bankofamerica", "chase", "wellsfargo", "citibank", "hsbc",
]

# Soglia distanza Levenshtein per lookalike domain
LOOKALIKE_DISTANCE_THRESHOLD = 2

# Massimo email analizzate per scan
MAX_EMAILS_PER_SCAN = 100
# Finestra temporale scan: ultimi N giorni
SCAN_WINDOW_DAYS = 7


# ---------------------------------------------------------------------------
# Cifratura password
# ---------------------------------------------------------------------------

def _derive_fernet_key() -> bytes:
    """Deriva una chiave Fernet a 32 byte da settings.secret_key."""
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_password(plaintext: str) -> str:
    """Cifra la password IMAP. Restituisce stringa base64 Fernet-encoded."""
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    """Decifra la password IMAP."""
    f = Fernet(_derive_fernet_key())
    return f.decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Connessione IMAP
# ---------------------------------------------------------------------------

def _imap_connect_sync(host: str, port: int, email_addr: str, password: str, use_ssl: bool) -> bool:
    """Testa la connessione IMAP. Blocco sincrono — va wrappato con to_thread."""
    try:
        if use_ssl:
            conn = imaplib.IMAP4_SSL(host, port, timeout=10)
        else:
            conn = imaplib.IMAP4(host, port)
        conn.login(email_addr, password)
        conn.logout()
        return True
    except Exception as exc:
        logger.warning("imap_connect_failed", host=host, error=str(exc))
        return False


async def test_imap_connection(host: str, port: int, email_addr: str, password: str, use_ssl: bool) -> bool:
    """Async wrapper per il test di connessione IMAP."""
    return await asyncio.to_thread(_imap_connect_sync, host, port, email_addr, password, use_ssl)


# ---------------------------------------------------------------------------
# Fetch email via IMAP
# ---------------------------------------------------------------------------

def _fetch_emails_sync(
    host: str,
    port: int,
    email_addr: str,
    password: str,
    use_ssl: bool,
    days_back: int = SCAN_WINDOW_DAYS,
    max_count: int = MAX_EMAILS_PER_SCAN,
) -> List[Dict]:
    """
    Fetch delle email nella INBOX degli ultimi `days_back` giorni.
    Restituisce lista di dict con i campi necessari per l'analisi.
    Operazione passiva: SOLA LETTURA, non modifica mailbox.
    """
    results = []
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")

    try:
        if use_ssl:
            conn = imaplib.IMAP4_SSL(host, port, timeout=15)
        else:
            conn = imaplib.IMAP4(host, port)

        conn.login(email_addr, password)
        conn.select("INBOX", readonly=True)  # readonly=True: nessuna modifica

        status, data = conn.search(None, f"SINCE {since_date}")
        if status != "OK":
            return results

        message_nums = data[0].split()
        # Limita al massimo consentito, più recenti prima
        message_nums = message_nums[-max_count:]

        for num in message_nums:
            status, msg_data = conn.fetch(num, "(BODY.PEEK[HEADER])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw_header = msg_data[0][1]
            msg = email.message_from_bytes(raw_header)

            results.append({
                "raw_headers": dict(msg),
                "message_id": msg.get("Message-ID", ""),
                "subject": _decode_header_value(msg.get("Subject", "")),
                "from": msg.get("From", ""),
                "reply_to": msg.get("Reply-To", ""),
                "to": msg.get("To", email_addr),
                "date": msg.get("Date", ""),
                "received": msg.get_all("Received", []),
                "authentication_results": msg.get("Authentication-Results", ""),
                "dkim_signature": msg.get("DKIM-Signature", ""),
                "x_spam_status": msg.get("X-Spam-Status", ""),
            })

        conn.logout()
    except Exception as exc:
        logger.error("imap_fetch_failed", host=host, email=email_addr, error=str(exc))

    return results


def _decode_header_value(value: str) -> str:
    """Decodifica header MIME encoded-word."""
    try:
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)
    except Exception:
        return value


async def fetch_emails(
    host: str, port: int, email_addr: str, password: str, use_ssl: bool
) -> List[Dict]:
    """Async wrapper per il fetch IMAP."""
    return await asyncio.to_thread(
        _fetch_emails_sync, host, port, email_addr, password, use_ssl
    )


# ---------------------------------------------------------------------------
# Analisi phishing
# ---------------------------------------------------------------------------

def _levenshtein(s1: str, s2: str) -> int:
    """Calcola la distanza di Levenshtein tra due stringhe."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


def _extract_email_address(header_value: str) -> Optional[str]:
    """Estrae l'indirizzo email puro da un header (es. 'John Doe <john@example.com>')."""
    match = re.search(r"<([^>]+)>", header_value)
    if match:
        return match.group(1).lower().strip()
    # Nessuna parentesi angolari — potrebbe essere già l'indirizzo puro
    val = header_value.strip().lower()
    if "@" in val:
        return val
    return None


def _extract_display_name(header_value: str) -> Optional[str]:
    """Estrae il display name da un header (es. 'John Doe <john@example.com>' → 'John Doe')."""
    match = re.match(r'^"?([^"<]+)"?\s*<', header_value.strip())
    if match:
        return match.group(1).strip()
    return None


def _is_lookalike_domain(domain: str, reference_domains: List[str]) -> Optional[str]:
    """
    Controlla se `domain` è simile (lookalike) a uno dei `reference_domains`.
    Restituisce il dominio originale se rilevato, None altrimenti.
    """
    domain_base = domain.split(".")[0].lower()
    for ref in reference_domains:
        if domain_base == ref:
            return None  # Match esatto — non è lookalike
        dist = _levenshtein(domain_base, ref)
        if 0 < dist <= LOOKALIKE_DISTANCE_THRESHOLD:
            return ref
    return None


def _extract_links(text: str) -> List[str]:
    """Estrae URL dal corpo testuale (headers possono contenere link in X-Spam)."""
    urls = re.findall(r"https?://[^\s\"<>]+", text)
    filtered = []
    for url in urls:
        if not any(re.search(p, url) for p in TRUSTED_LINK_PATTERNS):
            filtered.append(url)
    return filtered[:20]  # max 20 link per email


def _parse_auth_results(auth_header: str) -> Dict[str, str]:
    """
    Parsa l'header Authentication-Results per estrarre spf/dkim/dmarc.
    Esempio: "mx.example.com; spf=pass dkim=fail dmarc=pass"
    """
    results = {"spf": "none", "dkim": "none", "dmarc": "none"}
    for proto in ("spf", "dkim", "dmarc"):
        match = re.search(rf"{proto}=(\w+)", auth_header, re.IGNORECASE)
        if match:
            results[proto] = match.group(1).lower()
    return results


def analyze_email_headers(email_data: Dict) -> Optional[Dict]:
    """
    Analizza gli header di un'email alla ricerca di indicatori di phishing.
    Restituisce un dict con i risultati se l'email è sospetta, None altrimenti.

    Indicatori analizzati:
    1. SPF/DKIM/DMARC fail
    2. From/Reply-To mismatch
    3. Display name spoofing (brand noto nel nome, dominio diverso)
    4. Lookalike domain
    5. Urgency keywords nel subject
    6. Suspicious links negli header X-Spam
    """
    reasons = []
    severity_weights = {"critical": 30, "high": 20, "medium": 10, "low": 5}
    total_weight = 0

    from_header = email_data.get("from", "")
    reply_to_header = email_data.get("reply_to", "")
    subject = email_data.get("subject", "").lower()
    auth_header = email_data.get("authentication_results", "")
    x_spam = email_data.get("x_spam_status", "")

    from_addr = _extract_email_address(from_header)
    from_domain = from_addr.split("@")[1] if from_addr and "@" in from_addr else ""
    display_name = _extract_display_name(from_header) or ""

    # 1. Auth header analysis
    auth = _parse_auth_results(auth_header)
    spf_result = auth["spf"]
    dkim_result = auth["dkim"]
    dmarc_result = auth["dmarc"]

    if spf_result == "fail":
        reasons.append({"type": "spf_fail", "severity": "high",
                         "detail": f"SPF check failed for {from_domain}"})
        total_weight += severity_weights["high"]
    elif spf_result == "softfail":
        reasons.append({"type": "spf_softfail", "severity": "medium",
                         "detail": f"SPF softfail for {from_domain}"})
        total_weight += severity_weights["medium"]

    if dkim_result == "fail":
        reasons.append({"type": "dkim_fail", "severity": "high",
                         "detail": "DKIM signature verification failed"})
        total_weight += severity_weights["high"]

    if dmarc_result == "fail":
        reasons.append({"type": "dmarc_fail", "severity": "critical",
                         "detail": f"DMARC check failed — possible spoofing of {from_domain}"})
        total_weight += severity_weights["critical"]

    # 2. From/Reply-To mismatch
    if reply_to_header:
        reply_to_addr = _extract_email_address(reply_to_header)
        if reply_to_addr and from_addr:
            from_dom = from_addr.split("@")[1] if "@" in from_addr else ""
            reply_dom = reply_to_addr.split("@")[1] if "@" in reply_to_addr else ""
            if from_dom and reply_dom and from_dom != reply_dom:
                reasons.append({
                    "type": "reply_to_mismatch",
                    "severity": "high",
                    "detail": f"Reply-To domain ({reply_dom}) differs from From domain ({from_dom})",
                })
                total_weight += severity_weights["high"]

    # 3. Display name spoofing
    if display_name:
        display_lower = display_name.lower().replace(" ", "")
        for brand in HIGH_VALUE_TARGETS:
            if brand in display_lower and from_domain and brand not in from_domain:
                reasons.append({
                    "type": "display_name_spoofing",
                    "severity": "critical",
                    "detail": f"Display name '{display_name}' impersonates '{brand}' but sends from {from_domain}",
                })
                total_weight += severity_weights["critical"]
                break

    # 4. Lookalike domain
    if from_domain:
        impersonated = _is_lookalike_domain(from_domain, HIGH_VALUE_TARGETS)
        if impersonated:
            reasons.append({
                "type": "lookalike_domain",
                "severity": "critical",
                "detail": f"Domain '{from_domain}' is a lookalike of '{impersonated}'",
            })
            total_weight += severity_weights["critical"]

    # 5. Urgency keywords nel subject
    matched_keywords = [kw for kw in URGENCY_KEYWORDS if kw in subject]
    if matched_keywords:
        reasons.append({
            "type": "urgency_keywords",
            "severity": "medium",
            "detail": f"Urgency keywords detected in subject: {matched_keywords[:5]}",
        })
        total_weight += severity_weights["medium"]

    # 6. Suspicious links negli header testuali
    combined_text = x_spam + " " + auth_header
    suspicious_links = _extract_links(combined_text)

    # Nessun indicatore trovato — email pulita
    if total_weight == 0:
        return None

    # Calcola severity e confidence
    if total_weight >= 50:
        severity = "critical"
    elif total_weight >= 30:
        severity = "high"
    elif total_weight >= 15:
        severity = "medium"
    else:
        severity = "low"

    confidence_pct = min(100, total_weight * 2)
    confidence = f"{confidence_pct}%"

    # Classifica il tipo di minaccia principale
    reason_types = {r["type"] for r in reasons}
    if "display_name_spoofing" in reason_types or "lookalike_domain" in reason_types:
        threat_type = "impersonation"
    elif "dmarc_fail" in reason_types or "reply_to_mismatch" in reason_types:
        threat_type = "spoofing"
    elif "urgency_keywords" in reason_types:
        threat_type = "phishing"
    else:
        threat_type = "suspicious"

    return {
        "severity": severity,
        "threat_type": threat_type,
        "confidence_score": confidence,
        "detection_reasons": reasons,
        "spf_result": spf_result,
        "dkim_result": dkim_result,
        "dmarc_result": dmarc_result,
        "suspicious_links": suspicious_links or None,
    }


# ---------------------------------------------------------------------------
# Orchestrazione scan account
# ---------------------------------------------------------------------------

async def scan_email_account(
    db: AsyncSession,
    account,  # EmailAccount instance
) -> Dict:
    """
    Scansiona la INBOX dell'account e persiste le minacce trovate.
    Restituisce un dict con statistiche.
    """
    from datetime import datetime, timezone
    from app.models.email_account import EmailAccount
    from app.models.email_threat import EmailThreat
    from sqlalchemy import select

    logger.info("email_scan_started", account_id=str(account.id), email=account.email_address)

    # Marca come in scansione
    account.last_scanned_at = datetime.now(timezone.utc)

    try:
        password = decrypt_password(account.encrypted_password)
    except Exception:
        account.last_scan_status = "error"
        await db.commit()
        logger.error("email_decrypt_failed", account_id=str(account.id))
        return {"status": "error", "reason": "decrypt_failed"}

    emails = await fetch_emails(
        host=account.imap_host,
        port=account.imap_port,
        email_addr=account.email_address,
        password=password,
        use_ssl=account.use_ssl,
    )

    threats_found = 0
    for em in emails:
        analysis = analyze_email_headers(em)
        if analysis is None:
            continue

        # Deduplicazione: evita di ripersistere lo stesso Message-ID
        msg_id = em.get("message_id", "").strip()
        if msg_id:
            existing = await db.execute(
                select(EmailThreat).where(
                    EmailThreat.organization_id == account.organization_id,
                    EmailThreat.message_id == msg_id,
                )
            )
            if existing.scalar_one_or_none():
                continue

        # Parsing data ricezione
        received_at = None
        try:
            from email.utils import parsedate_to_datetime
            date_str = em.get("date", "")
            if date_str:
                received_at = parsedate_to_datetime(date_str)
        except Exception:
            pass

        threat = EmailThreat(
            organization_id=account.organization_id,
            message_id=msg_id or None,
            subject=em.get("subject", "")[:1024] or None,
            sender=em.get("from", "unknown")[:512],
            recipient=em.get("to", account.email_address)[:512],
            received_at=received_at,
            severity=analysis["severity"],
            threat_type=analysis["threat_type"],
            confidence_score=analysis["confidence_score"],
            detection_reasons=analysis["detection_reasons"],
            spf_result=analysis["spf_result"],
            dkim_result=analysis["dkim_result"],
            dmarc_result=analysis["dmarc_result"],
            suspicious_links=analysis.get("suspicious_links"),
        )
        db.add(threat)
        threats_found += 1

    account.last_scan_status = "ok"
    account.threats_count = (account.threats_count or 0) + threats_found
    await db.commit()

    logger.info(
        "email_scan_completed",
        account_id=str(account.id),
        emails_analyzed=len(emails),
        threats_found=threats_found,
    )
    return {
        "status": "ok",
        "emails_analyzed": len(emails),
        "threats_found": threats_found,
    }
