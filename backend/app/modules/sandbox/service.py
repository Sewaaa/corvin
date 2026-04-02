"""
File Sandbox — service layer (analisi statica).

Pipeline:
1. Ricezione file → validazione size/MIME → salvataggio con nome UUID
2. Hash computation (MD5 + SHA256)
3. YARA scan (ruleset embedded — PE, ELF, Office macro, JS obfuscation, webshell)
4. VirusTotal hash lookup (read-only, nessun upload del file)
5. Metadata extraction (magic bytes, entropia, stringhe sospette)
6. Verdict finale: safe / suspicious / malicious

Sicurezza:
- File salvati con nome UUID (no path traversal)
- File MAI eseguiti
- Limite dimensione applicato prima di scrivere su disco
- VirusTotal: solo lookup per hash SHA256 (privacy-preserving)
"""
import hashlib
import math
import os
import re
import struct
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024
UPLOAD_DIR = settings.upload_dir

# MIME type permessi (allowlist)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/x-zip-compressed",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/x-tar",
    "application/gzip",
    "application/octet-stream",
    "application/x-executable",
    "application/x-dosexec",
    "application/x-sharedlib",
    "text/plain",
    "text/html",
    "text/javascript",
    "application/javascript",
    "application/x-python-code",
    "application/x-sh",
    "image/jpeg",
    "image/png",
    "image/gif",
}

# Estensioni ad alto rischio che meritano analisi approfondita
HIGH_RISK_EXTENSIONS = {
    ".exe", ".dll", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js",
    ".jar", ".class", ".py", ".sh", ".elf", ".so", ".dylib",
    ".doc", ".docm", ".xls", ".xlsm", ".ppt", ".pptm",
    ".hta", ".wsf", ".wsh", ".msi", ".msp",
}

VT_API_BASE = "https://www.virustotal.com/api/v3"

# ---------------------------------------------------------------------------
# YARA rules embedded (minimal portable ruleset — nessun file esterno)
# ---------------------------------------------------------------------------

YARA_RULES_SOURCE = r"""
rule PE_Executable {
    meta:
        description = "Windows PE executable (MZ header)"
        severity = "medium"
        category = "executable"
    strings:
        $mz = { 4D 5A }
        $pe = { 50 45 00 00 }
    condition:
        $mz at 0 and $pe
}

rule ELF_Executable {
    meta:
        description = "Linux/Unix ELF executable"
        severity = "medium"
        category = "executable"
    strings:
        $elf = { 7F 45 4C 46 }
    condition:
        $elf at 0
}

rule Office_Macro_Indicator {
    meta:
        description = "Office document with embedded macro indicators"
        severity = "high"
        category = "macro"
    strings:
        $vba1 = "VBA" nocase
        $vba2 = "AutoOpen" nocase
        $vba3 = "Document_Open" nocase
        $vba4 = "Auto_Open" nocase
        $shell = "Shell(" nocase
        $wscript = "WScript.Shell" nocase
    condition:
        2 of ($vba1, $vba2, $vba3, $vba4) or
        any of ($shell, $wscript)
}

rule Suspicious_PowerShell {
    meta:
        description = "Obfuscated or suspicious PowerShell patterns"
        severity = "high"
        category = "powershell"
    strings:
        $enc1 = "-EncodedCommand" nocase
        $enc2 = "-enc " nocase
        $bypass = "bypass" nocase
        $hidden = "-WindowStyle Hidden" nocase
        $iex = "Invoke-Expression" nocase
        $iex2 = "IEX(" nocase
        $download = "DownloadString" nocase
        $webclient = "Net.WebClient" nocase
    condition:
        2 of them
}

rule JS_Obfuscation {
    meta:
        description = "JavaScript obfuscation patterns"
        severity = "medium"
        category = "javascript"
    strings:
        $eval = /eval\s*\(/ nocase
        $unescape = /unescape\s*\(/ nocase
        $fromcharcode = "fromCharCode" nocase
        $atob = /atob\s*\(/ nocase
        $hex_str = /\\x[0-9a-fA-F]{2}/ nocase
    condition:
        3 of them
}

rule Webshell_PHP {
    meta:
        description = "PHP webshell indicators"
        severity = "critical"
        category = "webshell"
    strings:
        $php_tag = "<?php" nocase
        $eval = /eval\s*\(/ nocase
        $base64 = "base64_decode" nocase
        $system = /system\s*\(/ nocase
        $exec = /exec\s*\(/ nocase
        $shell_exec = "shell_exec" nocase
        $passthru = "passthru" nocase
        $cmd = "$_GET" nocase
        $post = "$_POST" nocase
        $request = "$_REQUEST" nocase
    condition:
        $php_tag and (
            ($eval and $base64) or
            any of ($system, $exec, $shell_exec, $passthru) and
            any of ($cmd, $post, $request)
        )
}

rule Suspicious_Network_Indicators {
    meta:
        description = "Hardcoded C2/network indicators"
        severity = "high"
        category = "network"
    strings:
        $ip_pattern = /\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b/
        $cmd_shell = "cmd.exe" nocase
        $powershell_url = /https?:\/\/[^\s"']{10,}\.ps1/ nocase
        $tor = ".onion" nocase
        $raw_socket = "socket.connect" nocase
    condition:
        2 of them
}

rule Packed_Binary {
    meta:
        description = "Possibly packed or compressed binary (UPX/MPRESS)"
        severity = "medium"
        category = "packer"
    strings:
        $upx0 = "UPX0"
        $upx1 = "UPX1"
        $upx2 = "UPX!"
        $mpress = ".MPRESS"
        $aspack = "ASPack"
        $petite = "PEtite"
    condition:
        any of them
}
"""


def _compile_yara_rules():
    """Compila le regole YARA embedded. Restituisce None se yara-python non è disponibile."""
    try:
        import yara
        return yara.compile(source=YARA_RULES_SOURCE)
    except ImportError:
        logger.warning("yara_not_available", reason="yara-python not installed")
        return None
    except Exception as exc:
        logger.error("yara_compile_failed", error=str(exc))
        return None


# Compile once at module load
_YARA_RULES = _compile_yara_rules()


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def ensure_upload_dir() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_stored_path(file_id: uuid.UUID, extension: str = "") -> str:
    """Restituisce il path di storage sicuro per un file (UUID + ext originale)."""
    safe_ext = re.sub(r"[^a-zA-Z0-9.]", "", extension)[:10]
    return os.path.join(UPLOAD_DIR, f"{file_id}{safe_ext}")


# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------

def compute_hashes(data: bytes) -> Tuple[str, str]:
    """Restituisce (md5_hex, sha256_hex)."""
    md5 = hashlib.md5(data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()
    return md5, sha256


# ---------------------------------------------------------------------------
# YARA scan
# ---------------------------------------------------------------------------

def run_yara_scan(data: bytes) -> List[Dict]:
    """
    Esegue la scansione YARA sul contenuto del file.
    Restituisce lista di match con nome regola, severity e categoria.
    """
    if _YARA_RULES is None:
        return []

    try:
        matches = _YARA_RULES.match(data=data)
        results = []
        for match in matches:
            meta = match.meta
            results.append({
                "rule": match.rule,
                "severity": meta.get("severity", "medium"),
                "category": meta.get("category", "unknown"),
                "description": meta.get("description", ""),
                "tags": list(match.tags),
            })
        return results
    except Exception as exc:
        logger.error("yara_scan_failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# VirusTotal hash lookup
# ---------------------------------------------------------------------------

async def virustotal_hash_lookup(sha256: str) -> Optional[Dict]:
    """
    Cerca il file su VirusTotal tramite SHA256 hash (nessun upload).
    Restituisce un dict con statistiche di rilevamento, o None se non trovato / API key assente.
    """
    api_key = settings.virustotal_api_key
    if not api_key:
        logger.debug("vt_skipped", reason="no_api_key")
        return None

    url = f"{VT_API_BASE}/files/{sha256}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"x-apikey": api_key})

        if resp.status_code == 404:
            return {"status": "not_found", "detections": 0, "total": 0}
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            stats = data.get("attributes", {}).get("last_analysis_stats", {})
            return {
                "status": "found",
                "detections": stats.get("malicious", 0) + stats.get("suspicious", 0),
                "total": sum(stats.values()),
                "malicious": stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "harmless": stats.get("harmless", 0),
                "undetected": stats.get("undetected", 0),
                "last_analysis_date": data.get("attributes", {}).get("last_analysis_date"),
            }
    except Exception as exc:
        logger.warning("vt_lookup_failed", sha256=sha256[:8], error=str(exc))

    return None


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def compute_entropy(data: bytes) -> float:
    """Calcola l'entropia di Shannon del file (0-8). Valori > 7.0 indicano cifraura/packing."""
    if not data:
        return 0.0
    counter = Counter(data)
    length = len(data)
    entropy = -sum(
        (count / length) * math.log2(count / length)
        for count in counter.values()
    )
    return round(entropy, 4)


def detect_file_type(data: bytes) -> Tuple[str, str]:
    """
    Rileva il tipo di file tramite magic bytes.
    Restituisce (mime_type, magic_description).
    Usa python-magic se disponibile, altrimenti fallback manuale.
    """
    try:
        import magic as libmagic
        mime = libmagic.from_buffer(data, mime=True)
        desc = libmagic.from_buffer(data)
        return mime, desc
    except (ImportError, Exception):
        pass

    # Fallback manuale sui magic bytes più comuni
    if data[:2] == b"MZ":
        return "application/x-dosexec", "PE32 executable (Windows)"
    if data[:4] == b"\x7fELF":
        return "application/x-elf", "ELF executable (Linux)"
    if data[:4] == b"%PDF":
        return "application/pdf", "PDF document"
    if data[:2] in (b"PK", b"\x50\x4b"):
        return "application/zip", "Zip archive"
    if data[:4] == b"Rar!":
        return "application/x-rar-compressed", "RAR archive"
    if data[:3] == b"\xef\xbb\xbf" or all(32 <= b < 127 or b in (9, 10, 13) for b in data[:64]):
        return "text/plain", "ASCII text"
    return "application/octet-stream", "Binary data"


def extract_suspicious_strings(data: bytes, max_results: int = 30) -> List[str]:
    """
    Estrae stringhe ASCII leggibili di lunghezza >= 6 dal file.
    Filtra quelle che corrispondono a pattern sospetti.
    """
    suspicious_patterns = [
        rb"https?://[^\x00-\x1f\x7f-\xff ]{8,}",
        rb"cmd\.exe",
        rb"powershell",
        rb"WScript\.Shell",
        rb"base64",
        rb"fromCharCode",
        rb"eval\(",
        rb"exec\(",
        rb"shell_exec",
        rb"/bin/sh",
        rb"/bin/bash",
        rb"nc\.exe",
        rb"netcat",
        rb"mimikatz",
        rb"meterpreter",
        rb"payload",
    ]
    found = set()
    for pattern in suspicious_patterns:
        for match in re.findall(pattern, data, re.IGNORECASE):
            try:
                found.add(match.decode("ascii", errors="ignore")[:200])
            except Exception:
                pass
            if len(found) >= max_results:
                break
    return list(found)


def check_pe_characteristics(data: bytes) -> Optional[Dict]:
    """Estrae informazioni basilari dall'header PE se il file è un eseguibile Windows."""
    if len(data) < 64 or data[:2] != b"MZ":
        return None
    try:
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 24 > len(data):
            return None
        if data[pe_offset:pe_offset + 4] != b"PE\x00\x00":
            return None
        machine = struct.unpack_from("<H", data, pe_offset + 4)[0]
        num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
        characteristics = struct.unpack_from("<H", data, pe_offset + 22)[0]
        return {
            "machine": hex(machine),
            "architecture": "x64" if machine == 0x8664 else "x86" if machine == 0x14C else "unknown",
            "num_sections": num_sections,
            "is_dll": bool(characteristics & 0x2000),
            "is_executable": bool(characteristics & 0x0002),
        }
    except Exception:
        return None


def extract_metadata(data: bytes, original_filename: str) -> Dict:
    """
    Metadati aggregati: tipo file, entropia, stringhe sospette, caratteristiche PE.
    """
    ext = os.path.splitext(original_filename)[1].lower()
    mime_type, magic_desc = detect_file_type(data)
    entropy = compute_entropy(data)
    suspicious_strings = extract_suspicious_strings(data)
    pe_info = check_pe_characteristics(data)

    return {
        "file_extension": ext,
        "detected_mime": mime_type,
        "magic_description": magic_desc,
        "entropy": entropy,
        "high_entropy": entropy > 7.0,
        "suspicious_strings": suspicious_strings,
        "pe_info": pe_info,
        "is_high_risk_extension": ext in HIGH_RISK_EXTENSIONS,
        "file_size_bytes": len(data),
    }


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def calculate_verdict(
    yara_matches: List[Dict],
    vt_result: Optional[Dict],
    metadata: Dict,
) -> str:
    """
    Calcola il verdetto finale: safe / suspicious / malicious.

    Criteri malicious:
    - YARA match con severity=critical o categoria webshell
    - VT detections >= 5
    - YARA critical + VT positivo

    Criteri suspicious:
    - YARA match con severity >= high
    - VT detections 1-4
    - Entropia > 7.0 con estensione ad alto rischio
    - Stringhe sospette + YARA match
    """
    # VirusTotal malicious
    if vt_result and vt_result.get("malicious", 0) >= 5:
        return "malicious"

    # YARA critical
    critical_rules = [m for m in yara_matches if m.get("severity") == "critical"]
    if critical_rules:
        return "malicious"

    # Webshell
    webshell_rules = [m for m in yara_matches if m.get("category") == "webshell"]
    if webshell_rules:
        return "malicious"

    # VT sospetto
    if vt_result and vt_result.get("detections", 0) >= 1:
        return "suspicious"

    # YARA high
    high_rules = [m for m in yara_matches if m.get("severity") == "high"]
    if high_rules:
        return "suspicious"

    # Entropia alta + estensione rischiosa
    if metadata.get("high_entropy") and metadata.get("is_high_risk_extension"):
        return "suspicious"

    # Stringhe sospette + almeno 1 YARA match
    if metadata.get("suspicious_strings") and yara_matches:
        return "suspicious"

    return "safe"


# ---------------------------------------------------------------------------
# Orchestrazione analisi
# ---------------------------------------------------------------------------

async def analyze_file(
    db,
    sandbox_file,
    file_data: bytes,
) -> None:
    """
    Esegue la pipeline completa di analisi su un SandboxFile.
    Aggiorna il record in-place e fa commit.
    """
    from app.models.sandbox import FileStatus

    sandbox_file.status = FileStatus.ANALYZING
    await db.commit()

    try:
        # 1. Hash
        md5, sha256 = compute_hashes(file_data)
        sandbox_file.md5_hash = md5
        sandbox_file.sha256_hash = sha256

        # 2. YARA
        yara_matches = run_yara_scan(file_data)

        # 3. VirusTotal
        vt_result = await virustotal_hash_lookup(sha256)

        # 4. Metadata
        metadata = extract_metadata(file_data, sandbox_file.original_filename)
        mime_type = metadata.get("detected_mime")
        magic_desc = metadata.get("magic_description")

        # 5. Verdict
        verdict = calculate_verdict(yara_matches, vt_result, metadata)

        sandbox_file.mime_type = mime_type
        sandbox_file.file_magic = magic_desc
        sandbox_file.yara_matches = yara_matches
        sandbox_file.virustotal_result = vt_result
        sandbox_file.metadata_extracted = metadata
        sandbox_file.status = FileStatus[verdict.upper()]
        sandbox_file.analyzed_at = datetime.now(timezone.utc)

        logger.info(
            "sandbox_analysis_completed",
            file_id=str(sandbox_file.id),
            verdict=verdict,
            yara_hits=len(yara_matches),
            vt_detections=vt_result.get("detections") if vt_result else None,
        )

    except Exception as exc:
        logger.error("sandbox_analysis_failed", file_id=str(sandbox_file.id), error=str(exc))
        sandbox_file.status = FileStatus.SUSPICIOUS  # fail-safe: non marcare come safe

    await db.commit()
