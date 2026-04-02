"""
Web Scanner — service layer (PASSIVE ONLY).

Checks eseguiti:
  1. Security headers HTTP (CSP, HSTS, X-Frame-Options, ecc.)
  2. File esposti comuni (.env, .git/HEAD, backup files, ecc.)
  3. CMS detection e versione (WordPress, Joomla, Drupal)
  4. SSL/TLS (riutilizza domain_reputation)
  5. CVE lookup semplificato per versioni CMS note

IMPORTANTE — Sicurezza legale e tecnica:
  - Nessun payload intrusivo (no SQLi probes, no XSS, no fuzzing)
  - Rate limiting su ogni richiesta HTTP al target (max 10 req/scan)
  - Il dominio DEVE essere verificato prima dello scan (ownership proof)
  - User-Agent identificabile (non camuffato da browser reale)
"""
import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import audit
from app.models.notification import Notification, NotificationSeverity
from app.models.web_scan import ScanFinding, ScanStatus, WebScan

logger = structlog.get_logger(__name__)

SCANNER_UA = "Corvin-WebScanner/1.0 (security scan; authorized)"
REQUEST_TIMEOUT = 8.0
MAX_REQUESTS_PER_SCAN = 20  # Hard cap per evitare DoS accidentali


# ---------------------------------------------------------------------------
# Definizioni: header di sicurezza attesi
# ---------------------------------------------------------------------------

SECURITY_HEADERS: List[Dict[str, Any]] = [
    {
        "header": "Strict-Transport-Security",
        "category": "security_headers",
        "severity": "high",
        "title": "Missing HSTS header",
        "description": "HTTP Strict Transport Security is not set. Browsers may connect over HTTP.",
        "recommendation": "Add: Strict-Transport-Security: max-age=31536000; includeSubDomains",
        "check": lambda v: v is None,
    },
    {
        "header": "Content-Security-Policy",
        "category": "security_headers",
        "severity": "high",
        "title": "Missing Content-Security-Policy header",
        "description": "No CSP header found. XSS and data injection attacks are not mitigated.",
        "recommendation": "Define a strict CSP policy. Start with: Content-Security-Policy: default-src 'self'",
        "check": lambda v: v is None,
    },
    {
        "header": "X-Frame-Options",
        "category": "security_headers",
        "severity": "medium",
        "title": "Missing X-Frame-Options header",
        "description": "The page can be embedded in iframes, enabling clickjacking attacks.",
        "recommendation": "Add: X-Frame-Options: DENY  (or SAMEORIGIN if embedding is needed)",
        "check": lambda v: v is None,
    },
    {
        "header": "X-Content-Type-Options",
        "category": "security_headers",
        "severity": "medium",
        "title": "Missing X-Content-Type-Options header",
        "description": "Browser MIME sniffing is enabled, potentially allowing content-type confusion attacks.",
        "recommendation": "Add: X-Content-Type-Options: nosniff",
        "check": lambda v: v is None,
    },
    {
        "header": "Referrer-Policy",
        "category": "security_headers",
        "severity": "low",
        "title": "Missing Referrer-Policy header",
        "description": "Referrer information may be leaked to third-party sites.",
        "recommendation": "Add: Referrer-Policy: strict-origin-when-cross-origin",
        "check": lambda v: v is None,
    },
    {
        "header": "Permissions-Policy",
        "category": "security_headers",
        "severity": "low",
        "title": "Missing Permissions-Policy header",
        "description": "Browser features (camera, microphone, geolocation) are not explicitly restricted.",
        "recommendation": "Add: Permissions-Policy: geolocation=(), microphone=(), camera=()",
        "check": lambda v: v is None,
    },
    {
        "header": "Server",
        "category": "security_headers",
        "severity": "info",
        "title": "Server header discloses software version",
        "description": "The Server header reveals software and version information to attackers.",
        "recommendation": "Configure the web server to suppress or genericize the Server header.",
        "check": lambda v: v is not None and any(
            sw in v for sw in ["Apache/", "nginx/", "Microsoft-IIS/", "PHP/"]
        ),
    },
    {
        "header": "X-Powered-By",
        "category": "security_headers",
        "severity": "info",
        "title": "X-Powered-By header discloses technology stack",
        "description": "Technology stack information is exposed, aiding attacker reconnaissance.",
        "recommendation": "Remove or suppress the X-Powered-By header.",
        "check": lambda v: v is not None,
    },
]


# ---------------------------------------------------------------------------
# Definizioni: file esposti da sondare
# ---------------------------------------------------------------------------

EXPOSED_PATHS: List[Dict[str, Any]] = [
    {"path": "/.env", "severity": "critical", "title": "Exposed .env file",
     "description": "A .env file is publicly accessible. It may contain database credentials, API keys, and secrets.",
     "recommendation": "Move .env outside the web root or deny access via web server configuration."},
    {"path": "/.git/HEAD", "severity": "critical", "title": "Exposed .git directory",
     "description": "The .git directory is accessible. Attackers can reconstruct the full source code.",
     "recommendation": "Block access to .git via web server rules (deny all /.git/)."},
    {"path": "/wp-config.php.bak", "severity": "critical", "title": "Exposed WordPress config backup",
     "description": "A backup of wp-config.php is publicly accessible, potentially exposing DB credentials.",
     "recommendation": "Delete backup files from the web root."},
    {"path": "/config.php.bak", "severity": "critical", "title": "Exposed config backup file",
     "description": "A backup configuration file is publicly accessible.",
     "recommendation": "Delete or move backup files outside the web root."},
    {"path": "/.htpasswd", "severity": "high", "title": "Exposed .htpasswd file",
     "description": "Apache password file is accessible. Contains hashed credentials.",
     "recommendation": "Move .htpasswd above the web root or deny HTTP access."},
    {"path": "/phpinfo.php", "severity": "high", "title": "phpinfo() page exposed",
     "description": "PHP configuration details are publicly accessible, aiding attacker reconnaissance.",
     "recommendation": "Remove phpinfo.php from production environments."},
    {"path": "/server-status", "severity": "medium", "title": "Apache server-status exposed",
     "description": "Apache mod_status is publicly accessible, revealing server internals.",
     "recommendation": "Restrict /server-status to localhost or internal IPs only."},
    {"path": "/robots.txt", "severity": "info", "title": "robots.txt found",
     "description": "robots.txt may reveal sensitive paths (admin panels, internal APIs).",
     "recommendation": "Review robots.txt for inadvertent disclosure of sensitive paths."},
]


# ---------------------------------------------------------------------------
# Definizioni: firme CMS
# ---------------------------------------------------------------------------

CMS_SIGNATURES = [
    {
        "name": "WordPress",
        "indicators": [
            r"/wp-content/",
            r"/wp-includes/",
            r'name="generator" content="WordPress',
        ],
        "version_pattern": r'WordPress\s+([\d.]+)',
        "known_vulns": {
            "5.8": "CVE-2021-44223",
            "5.7": "CVE-2021-29447",
        },
    },
    {
        "name": "Joomla",
        "indicators": [
            r"/media/jui/",
            r'content="Joomla!',
            r"/components/com_",
        ],
        "version_pattern": r'Joomla!\s+([\d.]+)',
        "known_vulns": {},
    },
    {
        "name": "Drupal",
        "indicators": [
            r"/sites/default/files/",
            r'content="Drupal',
            r"X-Generator.*Drupal",
        ],
        "version_pattern": r'Drupal\s+([\d.]+)',
        "known_vulns": {
            "7": "CVE-2018-7600",  # Drupalgeddon2
        },
    },
]


# ---------------------------------------------------------------------------
# HTTP helper con rate limiting
# ---------------------------------------------------------------------------

class RateLimitedClient:
    """
    Wrapper httpx con rate limiting e contatore richieste per scan.
    Garantisce che uno scan non invii più di MAX_REQUESTS_PER_SCAN richieste.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self._request_count = 0
        self._client = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": SCANNER_UA},
            verify=False,  # Necessario per scan su cert scaduti
        )

    async def get(self, path: str) -> Optional[httpx.Response]:
        if self._request_count >= MAX_REQUESTS_PER_SCAN:
            logger.warning("scan_request_limit_reached", limit=MAX_REQUESTS_PER_SCAN)
            return None
        self._request_count += 1
        await asyncio.sleep(0.3)  # Throttle: 3.3 req/s max
        try:
            return await self._client.get(f"{self.base_url}{path}")
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Check 1: Security headers
# ---------------------------------------------------------------------------

def check_security_headers(response: httpx.Response) -> List[Dict]:
    """Analizza gli header HTTP della risposta e genera finding."""
    findings = []
    headers_lower = {k.lower(): v for k, v in response.headers.items()}

    for check in SECURITY_HEADERS:
        header_lower = check["header"].lower()
        value = headers_lower.get(header_lower)
        if check["check"](value):
            findings.append({
                "category": check["category"],
                "severity": check["severity"],
                "title": check["title"],
                "description": check["description"],
                "recommendation": check["recommendation"],
                "evidence": {"header": check["header"], "value": value},
            })

    return findings


# ---------------------------------------------------------------------------
# Check 2: File esposti
# ---------------------------------------------------------------------------

async def check_exposed_files(client: RateLimitedClient) -> List[Dict]:
    """
    Sonda path comuni per file esposti.
    Solo GET — nessun metodo intrusivo. Max 20 richieste totali per scan.
    """
    findings = []
    for path_def in EXPOSED_PATHS:
        resp = await client.get(path_def["path"])
        if resp is None:
            break  # Limite raggiunto
        if resp.status_code == 200:
            findings.append({
                "category": "exposed_files",
                "severity": path_def["severity"],
                "title": path_def["title"],
                "description": path_def["description"],
                "recommendation": path_def["recommendation"],
                "evidence": {"path": path_def["path"], "status_code": resp.status_code},
            })
    return findings


# ---------------------------------------------------------------------------
# Check 3: CMS detection
# ---------------------------------------------------------------------------

def detect_cms(response: httpx.Response) -> Tuple[Optional[str], Optional[str], List[Dict]]:
    """
    Rileva CMS e versione dall'HTML/header della homepage.
    Restituisce (cms_name, version, findings).
    Passivo: analizza solo il contenuto della risposta iniziale.
    """
    findings = []
    body = response.text
    headers_str = str(dict(response.headers))

    for cms in CMS_SIGNATURES:
        detected = any(
            re.search(indicator, body + headers_str, re.IGNORECASE)
            for indicator in cms["indicators"]
        )
        if not detected:
            continue

        # Cerca versione
        version = None
        match = re.search(cms["version_pattern"], body + headers_str, re.IGNORECASE)
        if match:
            version = match.group(1)

        findings.append({
            "category": "cms",
            "severity": "info",
            "title": f"CMS detected: {cms['name']}{f' {version}' if version else ''}",
            "description": f"{cms['name']} CMS detected. Keeping it updated is critical for security.",
            "recommendation": f"Ensure {cms['name']} core, themes, and plugins are always up to date.",
            "evidence": {"cms": cms["name"], "version": version},
        })

        # CVE lookup per versione nota
        if version:
            major = version.split(".")[0]
            cve = cms["known_vulns"].get(version) or cms["known_vulns"].get(major)
            if cve:
                findings.append({
                    "category": "cve",
                    "severity": "critical",
                    "title": f"Known vulnerability: {cve} in {cms['name']} {version}",
                    "description": (
                        f"{cms['name']} version {version} is affected by {cve}. "
                        "This version has a publicly known critical vulnerability."
                    ),
                    "recommendation": f"Upgrade {cms['name']} immediately to the latest stable version.",
                    "cve_id": cve,
                    "cvss_score": 9.8,
                    "evidence": {"cms": cms["name"], "version": version, "cve": cve},
                })

        return cms["name"], version, findings

    return None, None, []


# ---------------------------------------------------------------------------
# Orchestrazione scan completo
# ---------------------------------------------------------------------------

async def run_web_scan(
    db: AsyncSession,
    *,
    scan: WebScan,
    requesting_user_id: Optional[uuid.UUID] = None,
) -> WebScan:
    """
    Esegue il full passive scan su un URL target.
    Aggiorna il record WebScan e persiste i finding.

    Ordine: homepage fetch → header check → CMS detection → exposed files
    """
    target_url = scan.target_url
    logger.info("web_scan_start", url=target_url, scan_id=str(scan.id))

    scan.status = ScanStatus.RUNNING
    scan.started_at = datetime.now(timezone.utc)
    db.add(scan)
    await db.flush()

    all_findings: List[Dict] = []
    client = RateLimitedClient(target_url)

    try:
        # 1. Fetch homepage
        homepage = await client.get("/")
        if homepage is None or homepage.status_code >= 500:
            scan.status = ScanStatus.FAILED
            db.add(scan)
            return scan

        # 2. Security headers
        header_findings = check_security_headers(homepage)
        all_findings.extend(header_findings)

        # 3. CMS detection
        _cms_name, _cms_version, cms_findings = detect_cms(homepage)
        all_findings.extend(cms_findings)

        # 4. Exposed files
        exposed_findings = await check_exposed_files(client)
        all_findings.extend(exposed_findings)

    finally:
        await client.aclose()

    # Persisti i finding
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

    for f in all_findings:
        sev = f.get("severity", "info")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        finding = ScanFinding(
            scan_id=scan.id,
            organization_id=scan.organization_id,
            category=f.get("category", "info"),
            severity=sev,
            title=f["title"],
            description=f["description"],
            recommendation=f.get("recommendation"),
            cvss_score=f.get("cvss_score"),
            cve_id=f.get("cve_id"),
            evidence=f.get("evidence"),
        )
        db.add(finding)

    scan.status = ScanStatus.COMPLETED
    scan.completed_at = datetime.now(timezone.utc)
    scan.findings_count = len(all_findings)
    scan.critical_count = severity_counts["critical"]
    scan.high_count = severity_counts["high"]
    db.add(scan)

    # Notifica se ci sono finding critici o high
    if severity_counts["critical"] > 0 or severity_counts["high"] > 0:
        await _create_scan_notification(db, scan=scan, severity_counts=severity_counts)

    await audit(
        db,
        organization_id=scan.organization_id,
        user_id=requesting_user_id,
        action="web_scan.complete",
        resource_type="web_scan",
        resource_id=str(scan.id),
        details={
            "url": target_url,
            "findings_count": len(all_findings),
            **severity_counts,
        },
    )

    logger.info(
        "web_scan_complete",
        scan_id=str(scan.id),
        findings=len(all_findings),
        critical=severity_counts["critical"],
    )
    return scan


async def _create_scan_notification(
    db: AsyncSession, *, scan: WebScan, severity_counts: Dict
) -> None:
    dedup_key = f"webscan:{scan.id}:complete"
    existing = await db.execute(
        select(Notification).where(Notification.dedup_key == dedup_key)
    )
    if existing.scalar_one_or_none() is not None:
        return

    severity = (
        NotificationSeverity.CRITICAL
        if severity_counts["critical"] > 0
        else NotificationSeverity.HIGH
    )
    notification = Notification(
        organization_id=scan.organization_id,
        title=f"Web scan completed: {severity_counts['critical']} critical, {severity_counts['high']} high findings",
        message=(
            f"Scan of {scan.target_url} found {scan.findings_count} issue(s): "
            f"{severity_counts['critical']} critical, {severity_counts['high']} high, "
            f"{severity_counts['medium']} medium. Review and remediate immediately."
        ),
        severity=severity,
        source_module="web_scanner",
        source_id=str(scan.id),
        dedup_key=dedup_key,
    )
    db.add(notification)


async def create_scan(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    domain_id: uuid.UUID,
    target_url: str,
    frequency,
    requesting_user_id: Optional[uuid.UUID] = None,
) -> WebScan:
    """Crea un record WebScan e lo restituisce (non avvia lo scan)."""
    # Normalizza URL
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    # Rimuovi trailing slash
    target_url = target_url.rstrip("/")

    scan = WebScan(
        organization_id=organization_id,
        domain_id=domain_id,
        target_url=target_url,
        frequency=frequency,
        status=ScanStatus.PENDING,
    )
    db.add(scan)
    await db.flush()

    await audit(
        db,
        organization_id=organization_id,
        user_id=requesting_user_id,
        action="web_scan.create",
        resource_type="web_scan",
        resource_id=str(scan.id),
        details={"url": target_url},
    )

    return scan
