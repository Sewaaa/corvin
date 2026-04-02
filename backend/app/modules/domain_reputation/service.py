"""
Domain Reputation — service layer.

Esegue check passivi su un dominio:
  - DNS: MX, SPF, DMARC, NS (via dnspython)
  - DNSBL: verifica sulle blacklist più comuni
  - SSL: validità e scadenza del certificato (via ssl/socket)
  - WHOIS: registrar, date registrazione/scadenza (via python-whois)
  - Scoring: punteggio 0-100 basato sui finding

Nessun payload intrusivo viene inviato al target — solo query DNS e
connessioni SSL standard. Il dominio deve essere verificato (TXT record)
prima che scans intrusivi possano essere eseguiti — per ora solo passivi.
"""
import hashlib
import secrets
import socket
import ssl
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import dns.resolver
import dns.exception
import structlog
import whois

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.models.domain import Domain
from app.models.notification import Notification, NotificationSeverity

logger = structlog.get_logger(__name__)

# DNSBL più comuni (aggiunte in ordine di rilevanza)
DNSBL_ZONES = [
    "zen.spamhaus.org",
    "bl.spamcop.net",
    "dnsbl.sorbs.net",
    "b.barracudacentral.org",
    "dnsbl-1.uceprotect.net",
]

VERIFICATION_PREFIX = "corvin-verify="


# ---------------------------------------------------------------------------
# Ownership verification
# ---------------------------------------------------------------------------

def generate_verification_token() -> str:
    """Genera un token DNS TXT univoco per la verifica del dominio."""
    return f"{VERIFICATION_PREFIX}{secrets.token_hex(16)}"


async def verify_domain_ownership(
    db: AsyncSession,
    *,
    domain_obj: Domain,
) -> bool:
    """
    Controlla se il record TXT corvin-verify=<token> è presente nel DNS.
    Aggiorna domain_obj.is_verified e restituisce True se verificato.
    """
    if not domain_obj.verification_token:
        return False

    try:
        answers = dns.resolver.resolve(domain_obj.domain, "TXT")
        for rdata in answers:
            for txt_string in rdata.strings:
                if txt_string.decode("utf-8", errors="ignore") == domain_obj.verification_token:
                    domain_obj.is_verified = True
                    db.add(domain_obj)
                    logger.info("domain_verified", domain=domain_obj.domain)
                    return True
    except (dns.exception.DNSException, Exception) as exc:
        logger.warning("domain_verify_dns_error", domain=domain_obj.domain, error=str(exc))

    return False


# ---------------------------------------------------------------------------
# DNS checks
# ---------------------------------------------------------------------------

def _resolve_safe(domain: str, record_type: str) -> List[str]:
    """Esegue una query DNS restituendo una lista di stringhe. Silenzia errori."""
    try:
        answers = dns.resolver.resolve(domain, record_type, lifetime=5.0)
        return [r.to_text() for r in answers]
    except dns.resolver.NXDOMAIN:
        return []
    except dns.resolver.NoAnswer:
        return []
    except dns.exception.DNSException:
        return []
    except Exception:
        return []


def check_dns_records(domain: str) -> Dict[str, Any]:
    """
    Controlla i record DNS fondamentali per sicurezza email.
    Restituisce un dict con i record trovati e le anomalie rilevate.
    """
    records: Dict[str, Any] = {}
    findings: List[Dict] = []

    # MX
    mx = _resolve_safe(domain, "MX")
    records["mx"] = mx
    if not mx:
        findings.append({"type": "no_mx_record", "severity": "medium",
                         "title": "No MX record found",
                         "detail": f"{domain} has no MX records — email delivery may be misconfigured."})

    # SPF (cerca nei TXT)
    txt_records = _resolve_safe(domain, "TXT")
    records["txt"] = txt_records
    spf = [r for r in txt_records if "v=spf1" in r]
    records["spf"] = spf
    if not spf:
        findings.append({"type": "no_spf_record", "severity": "high",
                         "title": "No SPF record",
                         "detail": "Missing SPF record allows anyone to spoof email from this domain."})
    elif len(spf) > 1:
        findings.append({"type": "multiple_spf_records", "severity": "medium",
                         "title": "Multiple SPF records",
                         "detail": "Only one SPF record is allowed. Multiple records cause validation failures."})

    # DMARC
    dmarc_records = _resolve_safe(f"_dmarc.{domain}", "TXT")
    dmarc = [r for r in dmarc_records if "v=DMARC1" in r]
    records["dmarc"] = dmarc
    if not dmarc:
        findings.append({"type": "no_dmarc_record", "severity": "high",
                         "title": "No DMARC record",
                         "detail": "Missing DMARC policy — phishing and spoofing attacks are not blocked."})
    else:
        # Controlla policy (p=none è debole)
        dmarc_str = dmarc[0] if dmarc else ""
        if "p=none" in dmarc_str:
            findings.append({"type": "dmarc_policy_none", "severity": "medium",
                             "title": "DMARC policy is p=none",
                             "detail": "DMARC policy 'none' only monitors — it does not reject spoofed emails. "
                                       "Upgrade to p=quarantine or p=reject."})

    # NS
    ns = _resolve_safe(domain, "NS")
    records["ns"] = ns

    return {"records": records, "findings": findings}


# ---------------------------------------------------------------------------
# DNSBL check
# ---------------------------------------------------------------------------

def _get_domain_ips(domain: str) -> List[str]:
    """Risolve il dominio in IP (A record)."""
    try:
        return [r for r in _resolve_safe(domain, "A")]
    except Exception:
        return []


def _reverse_ip(ip: str) -> str:
    """Inverte l'IP per le query DNSBL: 1.2.3.4 → 4.3.2.1"""
    return ".".join(reversed(ip.split(".")))


def check_dnsbl(domain: str) -> Dict[str, Any]:
    """
    Controlla se il dominio o i suoi IP sono nelle DNSBL principali.
    Usa query DNS standard — nessuna connessione ai server DNSBL.
    """
    ips = _get_domain_ips(domain)
    listed_on: List[str] = []
    checked: List[str] = []

    for ip in ips[:4]:  # max 4 IP per evitare timeout eccessivi
        reversed_ip = _reverse_ip(ip)
        for dnsbl in DNSBL_ZONES:
            query = f"{reversed_ip}.{dnsbl}"
            checked.append(dnsbl)
            try:
                dns.resolver.resolve(query, "A", lifetime=3.0)
                listed_on.append(f"{dnsbl} (IP: {ip})")
                logger.warning("domain_blacklisted", domain=domain, dnsbl=dnsbl, ip=ip)
            except dns.resolver.NXDOMAIN:
                pass  # Non in blacklist
            except dns.exception.DNSException:
                pass  # Timeout o errore — skip

    findings = []
    if listed_on:
        findings.append({
            "type": "dnsbl_listed",
            "severity": "critical",
            "title": f"Domain listed on {len(listed_on)} DNSBL(s)",
            "detail": f"Listed on: {', '.join(listed_on)}. "
                      "This severely impacts email deliverability and domain reputation.",
        })

    return {
        "ips_checked": ips,
        "dnsbl_zones_checked": len(set(checked)),
        "listed_on": listed_on,
        "is_blacklisted": bool(listed_on),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# SSL check
# ---------------------------------------------------------------------------

def check_ssl(domain: str) -> Dict[str, Any]:
    """
    Controlla il certificato SSL del dominio: validità, scadenza, CN.
    Usa socket + ssl standard — nessuna dipendenza esterna.
    """
    findings: List[Dict] = []
    result: Dict[str, Any] = {"valid": False, "expiry": None, "days_remaining": None}

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

        not_after_str = cert.get("notAfter", "")
        if not_after_str:
            expiry = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(
                tzinfo=timezone.utc
            )
            days_remaining = (expiry - datetime.now(timezone.utc)).days
            result["valid"] = True
            result["expiry"] = expiry.date().isoformat()
            result["days_remaining"] = days_remaining

            if days_remaining < 0:
                findings.append({"type": "ssl_expired", "severity": "critical",
                                 "title": "SSL certificate has expired",
                                 "detail": f"Certificate expired {abs(days_remaining)} day(s) ago."})
            elif days_remaining < 14:
                findings.append({"type": "ssl_expiry_critical", "severity": "critical",
                                 "title": f"SSL certificate expires in {days_remaining} days",
                                 "detail": "Renew immediately to avoid service disruption."})
            elif days_remaining < 30:
                findings.append({"type": "ssl_expiry_soon", "severity": "high",
                                 "title": f"SSL certificate expires in {days_remaining} days",
                                 "detail": "Schedule renewal within the next two weeks."})

    except ssl.SSLCertVerificationError as exc:
        findings.append({"type": "ssl_invalid_cert", "severity": "critical",
                         "title": "SSL certificate validation failed",
                         "detail": str(exc)})
    except ConnectionRefusedError:
        findings.append({"type": "ssl_no_https", "severity": "high",
                         "title": "HTTPS not available",
                         "detail": f"{domain} does not accept connections on port 443."})
    except (socket.timeout, OSError) as exc:
        findings.append({"type": "ssl_unreachable", "severity": "medium",
                         "title": "SSL check failed — host unreachable",
                         "detail": str(exc)})

    result["findings"] = findings
    return result


# ---------------------------------------------------------------------------
# WHOIS
# ---------------------------------------------------------------------------

def check_whois(domain: str) -> Dict[str, Any]:
    """
    Recupera dati WHOIS. Gestisce timeout e domini con privacy shield.
    Rileva registrazioni recenti (possibile dominio di phishing).
    """
    findings: List[Dict] = []
    result: Dict[str, Any] = {}

    try:
        w = whois.whois(domain)
        creation = w.creation_date
        expiration = w.expiration_date

        # python-whois restituisce a volte liste, a volte singoli valori
        if isinstance(creation, list):
            creation = creation[0]
        if isinstance(expiration, list):
            expiration = expiration[0]

        if creation:
            result["creation_date"] = creation.isoformat() if hasattr(creation, "isoformat") else str(creation)
            age_days = (datetime.now() - creation.replace(tzinfo=None)).days
            if age_days < 30:
                findings.append({"type": "recently_registered", "severity": "high",
                                 "title": f"Domain registered {age_days} days ago",
                                 "detail": "Recently registered domains are often used for phishing campaigns."})

        if expiration:
            result["expiration_date"] = expiration.isoformat() if hasattr(expiration, "isoformat") else str(expiration)

        result["registrar"] = w.registrar
        result["name_servers"] = w.name_servers

    except Exception as exc:
        logger.debug("whois_failed", domain=domain, error=str(exc))
        result["error"] = "WHOIS lookup failed or data unavailable"

    result["findings"] = findings
    return result


# ---------------------------------------------------------------------------
# Reputation scoring
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {"critical": 30, "high": 15, "medium": 8, "low": 3}


def calculate_reputation_score(all_findings: List[Dict]) -> int:
    """
    Calcola un punteggio reputazione 0-100 (100 = completamente pulito).
    Scala: ≥80 verde, 50-79 giallo, 20-49 arancione, <20 rosso.
    """
    deductions = sum(
        SEVERITY_WEIGHTS.get(f.get("severity", "low"), 3)
        for f in all_findings
    )
    return max(0, 100 - deductions)


# ---------------------------------------------------------------------------
# Full scan orchestration
# ---------------------------------------------------------------------------

async def run_domain_scan(
    db: AsyncSession,
    *,
    domain_obj: Domain,
    requesting_user_id: Optional[uuid.UUID] = None,
) -> Domain:
    """
    Esegue il full scan passivo su un dominio:
    DNS → DNSBL → SSL → WHOIS → scoring → salvataggio risultati.
    """
    domain_name = domain_obj.domain
    logger.info("domain_scan_start", domain=domain_name)

    all_findings: List[Dict] = []

    # 1. DNS
    dns_result = check_dns_records(domain_name)
    all_findings.extend(dns_result["findings"])

    # 2. DNSBL
    dnsbl_result = check_dnsbl(domain_name)
    all_findings.extend(dnsbl_result["findings"])

    # 3. SSL
    ssl_result = check_ssl(domain_name)
    all_findings.extend(ssl_result["findings"])

    # 4. WHOIS
    whois_result = check_whois(domain_name)
    all_findings.extend(whois_result.pop("findings", []))

    # 5. Scoring
    reputation_score = calculate_reputation_score(all_findings)

    # 6. Aggiorna Domain
    domain_obj.dns_records = dns_result["records"]
    domain_obj.scan_findings = all_findings
    domain_obj.whois_data = whois_result
    domain_obj.is_blacklisted = dnsbl_result["is_blacklisted"]
    domain_obj.reputation_score = reputation_score
    domain_obj.last_scan_at = datetime.now(timezone.utc)

    if ssl_result.get("expiry"):
        from datetime import date as date_type
        domain_obj.ssl_expiry = date_type.fromisoformat(ssl_result["expiry"])

    db.add(domain_obj)

    # 7. Notifiche per finding critici
    critical = [f for f in all_findings if f.get("severity") == "critical"]
    if critical or dnsbl_result["is_blacklisted"]:
        await _create_domain_notification(
            db, domain_obj=domain_obj, findings=all_findings, score=reputation_score
        )

    await audit(
        db,
        organization_id=domain_obj.organization_id,
        user_id=requesting_user_id,
        action="domain.scan",
        resource_type="domain",
        resource_id=str(domain_obj.id),
        details={
            "findings_count": len(all_findings),
            "reputation_score": reputation_score,
            "is_blacklisted": dnsbl_result["is_blacklisted"],
        },
    )

    logger.info(
        "domain_scan_complete",
        domain=domain_name,
        score=reputation_score,
        findings=len(all_findings),
    )
    return domain_obj


async def _create_domain_notification(
    db: AsyncSession,
    *,
    domain_obj: Domain,
    findings: List[Dict],
    score: int,
) -> None:
    """Crea un alert per reputazione degradata o finding critici. Deduplicato per scan."""
    dedup_key = f"domain:{domain_obj.id}:score:{score}"

    existing = await db.execute(
        select(Notification).where(Notification.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none() is not None:
        return

    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    severity = NotificationSeverity.CRITICAL if critical_count > 0 else NotificationSeverity.HIGH

    notification = Notification(
        organization_id=domain_obj.organization_id,
        title=f"Domain reputation degraded: {domain_obj.domain} (score: {score}/100)",
        message=(
            f"Scan found {len(findings)} issue(s) including {critical_count} critical "
            f"for {domain_obj.domain}. Immediate review recommended."
        ),
        severity=severity,
        source_module="domain_reputation",
        source_id=str(domain_obj.id),
        dedup_key=dedup_key,
    )
    db.add(notification)


async def add_domain(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    domain_name: str,
    requesting_user_id: Optional[uuid.UUID] = None,
) -> Domain:
    """
    Aggiunge un dominio all'organizzazione e genera il token di verifica.
    Il dominio NON viene scansionato finché non è verificato.
    """
    # Controlla duplicati nel tenant
    existing = await db.execute(
        select(Domain).where(
            Domain.organization_id == organization_id,
            Domain.domain == domain_name,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Domain '{domain_name}' is already added to this organization")

    token = generate_verification_token()
    domain_obj = Domain(
        organization_id=organization_id,
        domain=domain_name,
        verification_token=token,
        is_verified=False,
    )
    db.add(domain_obj)
    await db.flush()

    await audit(
        db,
        organization_id=organization_id,
        user_id=requesting_user_id,
        action="domain.add",
        resource_type="domain",
        resource_id=str(domain_obj.id),
        details={"domain": domain_name},
    )

    return domain_obj
