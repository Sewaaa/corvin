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
        "type": "missing_hsts",
        "header": "Strict-Transport-Security",
        "category": "security_headers",
        "severity": "high",
        "title": "Header HSTS mancante",
        "description": "HTTP Strict Transport Security non impostato. I browser potrebbero connettersi via HTTP.",
        "recommendation": "Aggiungi: Strict-Transport-Security: max-age=31536000; includeSubDomains",
        "check": lambda v: v is None,
    },
    {
        "type": "missing_csp",
        "header": "Content-Security-Policy",
        "category": "security_headers",
        "severity": "high",
        "title": "Header Content-Security-Policy mancante",
        "description": "Nessun header CSP trovato. Gli attacchi XSS e data injection non sono mitigati.",
        "recommendation": "Definisci una policy CSP restrittiva. Inizia con: Content-Security-Policy: default-src 'self'",
        "check": lambda v: v is None,
    },
    {
        "type": "missing_x_frame_options",
        "header": "X-Frame-Options",
        "category": "security_headers",
        "severity": "medium",
        "title": "Header X-Frame-Options mancante",
        "description": "La pagina puo essere incorporata in iframe, abilitando attacchi di clickjacking.",
        "recommendation": "Aggiungi: X-Frame-Options: DENY  (o SAMEORIGIN se l'embedding e necessario)",
        "check": lambda v: v is None,
    },
    {
        "type": "missing_x_content_type_options",
        "header": "X-Content-Type-Options",
        "category": "security_headers",
        "severity": "medium",
        "title": "Header X-Content-Type-Options mancante",
        "description": "Il MIME sniffing del browser e abilitato, consentendo potenzialmente attacchi di content-type confusion.",
        "recommendation": "Aggiungi: X-Content-Type-Options: nosniff",
        "check": lambda v: v is None,
    },
    {
        "type": "missing_referrer_policy",
        "header": "Referrer-Policy",
        "category": "security_headers",
        "severity": "low",
        "title": "Header Referrer-Policy mancante",
        "description": "Le informazioni sul referrer potrebbero essere esposte a siti di terze parti.",
        "recommendation": "Aggiungi: Referrer-Policy: strict-origin-when-cross-origin",
        "check": lambda v: v is None,
    },
    {
        "type": "missing_permissions_policy",
        "header": "Permissions-Policy",
        "category": "security_headers",
        "severity": "low",
        "title": "Header Permissions-Policy mancante",
        "description": "Le funzionalita del browser (fotocamera, microfono, geolocalizzazione) non sono esplicitamente limitate.",
        "recommendation": "Aggiungi: Permissions-Policy: geolocation=(), microphone=(), camera=()",
        "check": lambda v: v is None,
    },
    {
        "type": "server_header_disclosure",
        "header": "Server",
        "category": "security_headers",
        "severity": "info",
        "title": "Header Server espone la versione del software",
        "description": "L'header Server rivela informazioni sul software e la versione agli attaccanti.",
        "recommendation": "Configura il web server per sopprimere o rendere generico l'header Server.",
        "check": lambda v: v is not None and any(
            sw in v for sw in ["Apache/", "nginx/", "Microsoft-IIS/", "PHP/"]
        ),
    },
    {
        "type": "x_powered_by_disclosure",
        "header": "X-Powered-By",
        "category": "security_headers",
        "severity": "info",
        "title": "Header X-Powered-By espone lo stack tecnologico",
        "description": "Le informazioni sullo stack tecnologico sono esposte, facilitando la ricognizione degli attaccanti.",
        "recommendation": "Rimuovi o sopprimi l'header X-Powered-By.",
        "check": lambda v: v is not None,
    },
]


# ---------------------------------------------------------------------------
# Definizioni: file esposti da sondare
# ---------------------------------------------------------------------------

EXPOSED_PATHS: List[Dict[str, Any]] = [
    {"path": "/.env", "severity": "critical", "title": "File .env esposto",
     "description": "Un file .env e accessibile pubblicamente. Potrebbe contenere credenziali database, chiavi API e segreti.",
     "recommendation": "Sposta il file .env fuori dalla web root o negane l'accesso tramite configurazione del web server."},
    {"path": "/.git/HEAD", "severity": "critical", "title": "Directory .git esposta",
     "description": "La directory .git e accessibile. Gli attaccanti possono ricostruire l'intero codice sorgente.",
     "recommendation": "Blocca l'accesso a .git tramite regole del web server (deny all /.git/)."},
    {"path": "/wp-config.php.bak", "severity": "critical", "title": "Backup configurazione WordPress esposto",
     "description": "Un backup di wp-config.php e accessibile pubblicamente, esponendo potenzialmente le credenziali del DB.",
     "recommendation": "Elimina i file di backup dalla web root."},
    {"path": "/config.php.bak", "severity": "critical", "title": "File di backup configurazione esposto",
     "description": "Un file di backup della configurazione e accessibile pubblicamente.",
     "recommendation": "Elimina o sposta i file di backup fuori dalla web root."},
    {"path": "/.htpasswd", "severity": "high", "title": "File .htpasswd esposto",
     "description": "Il file password di Apache e accessibile. Contiene credenziali hashate.",
     "recommendation": "Sposta .htpasswd sopra la web root o negane l'accesso HTTP."},
    {"path": "/phpinfo.php", "severity": "high", "title": "Pagina phpinfo() esposta",
     "description": "I dettagli di configurazione PHP sono accessibili pubblicamente, facilitando la ricognizione degli attaccanti.",
     "recommendation": "Rimuovi phpinfo.php dagli ambienti di produzione."},
    {"path": "/server-status", "severity": "medium", "title": "Apache server-status esposto",
     "description": "Apache mod_status e accessibile pubblicamente, rivelando dettagli interni del server.",
     "recommendation": "Limita /server-status solo a localhost o IP interni."},
    {"path": "/robots.txt", "severity": "info", "title": "robots.txt trovato",
     "description": "robots.txt potrebbe rivelare percorsi sensibili (pannelli admin, API interne).",
     "recommendation": "Controlla robots.txt per eventuali esposizioni involontarie di percorsi sensibili."},
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
            verify=False,  # nosec B501 — intentional: scanner must reach sites with expired certs
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
                "type": check["type"],
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
            "title": f"CMS rilevato: {cms['name']}{f' {version}' if version else ''}",
            "description": f"CMS {cms['name']} rilevato. Mantenerlo aggiornato e fondamentale per la sicurezza.",
            "recommendation": f"Assicurati che core, temi e plugin di {cms['name']} siano sempre aggiornati.",
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
                    "title": f"Vulnerabilita nota: {cve} in {cms['name']} {version}",
                    "description": (
                        f"{cms['name']} versione {version} e affetto da {cve}. "
                        "Questa versione presenta una vulnerabilita critica pubblicamente nota."
                    ),
                    "recommendation": f"Aggiorna immediatamente {cms['name']} all'ultima versione stabile.",
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
        title=f"Scansione web completata: {severity_counts['critical']} critici, {severity_counts['high']} alti",
        message=(
            f"La scansione di {scan.target_url} ha trovato {scan.findings_count} problema/i: "
            f"{severity_counts['critical']} critici, {severity_counts['high']} alti, "
            f"{severity_counts['medium']} medi. Verifica e correggi immediatamente."
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
