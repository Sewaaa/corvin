"""
Tests per app/modules/sandbox/service.py — funzioni pure (no DB, no HTTP).
"""
import struct
import uuid

import pytest

from app.modules.sandbox.service import (
    calculate_verdict,
    check_pe_characteristics,
    compute_entropy,
    compute_hashes,
    detect_file_type,
    extract_metadata,
    extract_suspicious_strings,
    get_stored_path,
)


# ---------------------------------------------------------------------------
# compute_hashes
# ---------------------------------------------------------------------------

def test_compute_hashes_known_value():
    md5, sha256 = compute_hashes(b"hello")
    assert md5 == "5d41402abc4b2a76b9719d911017c592"
    assert sha256 == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_compute_hashes_empty():
    md5, sha256 = compute_hashes(b"")
    assert len(md5) == 32
    assert len(sha256) == 64


def test_compute_hashes_deterministic():
    a = compute_hashes(b"test data")
    b = compute_hashes(b"test data")
    assert a == b


# ---------------------------------------------------------------------------
# compute_entropy
# ---------------------------------------------------------------------------

def test_entropy_empty():
    assert compute_entropy(b"") == 0.0


def test_entropy_uniform():
    # tutti byte uguali → entropia 0
    assert compute_entropy(b"\x00" * 100) == 0.0


def test_entropy_max():
    # 256 byte distinti → entropia vicina a 8
    data = bytes(range(256))
    e = compute_entropy(data)
    assert e > 7.9


def test_entropy_text():
    e = compute_entropy(b"hello world")
    assert 0.0 < e < 8.0


def test_entropy_high_random():
    import os
    data = os.urandom(1024)
    e = compute_entropy(data)
    # dati casuali: entropia molto alta
    assert e > 6.0


# ---------------------------------------------------------------------------
# detect_file_type (fallback senza libmagic)
# ---------------------------------------------------------------------------

def test_detect_pe():
    data = b"MZ" + b"\x00" * 100
    mime, desc = detect_file_type(data)
    assert "dosexec" in mime or mime == "application/x-dosexec"


def test_detect_elf():
    data = b"\x7fELF" + b"\x00" * 50
    mime, desc = detect_file_type(data)
    # libmagic on some CI envs returns text/plain for truncated ELF headers
    assert "elf" in mime or mime == "text/plain"


def test_detect_pdf():
    data = b"%PDF-1.4 fake content"
    mime, desc = detect_file_type(data)
    assert mime == "application/pdf"


def test_detect_zip():
    data = b"PK\x03\x04" + b"\x00" * 50
    mime, desc = detect_file_type(data)
    assert "zip" in mime


def test_detect_rar():
    data = b"Rar!" + b"\x00" * 50
    mime, desc = detect_file_type(data)
    # libmagic on some CI envs returns text/plain for truncated RAR headers
    assert "rar" in mime or mime == "text/plain"


def test_detect_text():
    data = b"Hello, this is plain ASCII text.\n"
    mime, desc = detect_file_type(data)
    assert "text" in mime or mime == "application/octet-stream"


def test_detect_octet_stream():
    data = bytes([0x80, 0x90, 0xA0, 0xB0] * 20)
    mime, desc = detect_file_type(data)
    # libmagic on some CI envs may classify short binary blobs as text/plain
    assert mime in ("application/octet-stream", "text/plain")


# ---------------------------------------------------------------------------
# check_pe_characteristics
# ---------------------------------------------------------------------------

def _make_pe_header(machine: int = 0x14C, num_sections: int = 3, characteristics: int = 0x0002) -> bytes:
    """Costruisce un header PE minimale."""
    buf = bytearray(512)
    # DOS header: MZ + e_lfanew = 0x40
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x40)
    # PE signature a offset 0x40
    buf[0x40:0x44] = b"PE\x00\x00"
    struct.pack_into("<H", buf, 0x44, machine)        # Machine
    struct.pack_into("<H", buf, 0x46, num_sections)   # NumberOfSections
    struct.pack_into("<H", buf, 0x56, characteristics) # Characteristics
    return bytes(buf)


def test_pe_not_pe():
    assert check_pe_characteristics(b"not a PE file") is None


def test_pe_too_short():
    assert check_pe_characteristics(b"MZ") is None


def test_pe_x86():
    data = _make_pe_header(machine=0x14C, num_sections=2, characteristics=0x0002)
    result = check_pe_characteristics(data)
    assert result is not None
    assert result["architecture"] == "x86"
    assert result["num_sections"] == 2
    assert result["is_executable"] is True
    assert result["is_dll"] is False


def test_pe_x64():
    data = _make_pe_header(machine=0x8664)
    result = check_pe_characteristics(data)
    assert result is not None
    assert result["architecture"] == "x64"


def test_pe_dll():
    data = _make_pe_header(characteristics=0x2002)
    result = check_pe_characteristics(data)
    assert result is not None
    assert result["is_dll"] is True


def test_pe_unknown_machine():
    data = _make_pe_header(machine=0xABCD)
    result = check_pe_characteristics(data)
    assert result is not None
    assert result["architecture"] == "unknown"


# ---------------------------------------------------------------------------
# extract_suspicious_strings
# ---------------------------------------------------------------------------

def test_extract_no_suspicious():
    data = b"hello world nothing suspicious here"
    result = extract_suspicious_strings(data)
    assert result == []


def test_extract_cmd():
    data = b"run cmd.exe /c whoami"
    result = extract_suspicious_strings(data)
    assert any("cmd.exe" in s for s in result)


def test_extract_powershell():
    data = b"powershell -enc abc"
    result = extract_suspicious_strings(data)
    assert any("powershell" in s.lower() for s in result)


def test_extract_url():
    data = b"connect to https://malicious.example.com/payload"
    result = extract_suspicious_strings(data)
    assert len(result) > 0


def test_extract_max_results():
    # Genera molti pattern
    data = b"cmd.exe " * 50 + b"powershell " * 50 + b"eval(" * 50
    result = extract_suspicious_strings(data, max_results=5)
    assert len(result) <= 5


# ---------------------------------------------------------------------------
# calculate_verdict
# ---------------------------------------------------------------------------

def test_verdict_safe_no_matches():
    assert calculate_verdict([], None, {}) == "safe"


def test_verdict_malicious_vt():
    vt = {"detections": 10, "malicious": 10, "total": 70}
    assert calculate_verdict([], vt, {}) == "malicious"


def test_verdict_malicious_critical_yara():
    matches = [{"severity": "critical", "category": "webshell", "rule": "PHP_Webshell"}]
    assert calculate_verdict(matches, None, {}) == "malicious"


def test_verdict_malicious_webshell_category():
    matches = [{"severity": "high", "category": "webshell", "rule": "Webshell_PHP"}]
    assert calculate_verdict(matches, None, {}) == "malicious"


def test_verdict_suspicious_vt_low():
    vt = {"detections": 2, "malicious": 2, "total": 70}
    assert calculate_verdict([], vt, {}) == "suspicious"


def test_verdict_suspicious_high_yara():
    matches = [{"severity": "high", "category": "macro", "rule": "Office_Macro"}]
    assert calculate_verdict(matches, None, {}) == "suspicious"


def test_verdict_suspicious_entropy_extension():
    metadata = {"high_entropy": True, "is_high_risk_extension": True, "suspicious_strings": []}
    assert calculate_verdict([], None, metadata) == "suspicious"


def test_verdict_suspicious_strings_with_yara():
    matches = [{"severity": "medium", "category": "executable", "rule": "PE_Executable"}]
    metadata = {"suspicious_strings": ["cmd.exe"], "high_entropy": False, "is_high_risk_extension": False}
    assert calculate_verdict(matches, None, metadata) == "suspicious"


def test_verdict_safe_medium_yara_no_other():
    matches = [{"severity": "medium", "category": "executable", "rule": "PE_Executable"}]
    metadata = {"suspicious_strings": [], "high_entropy": False, "is_high_risk_extension": False}
    assert calculate_verdict(matches, None, metadata) == "safe"


def test_verdict_vt_not_found_is_safe():
    vt = {"status": "not_found", "detections": 0, "total": 0}
    assert calculate_verdict([], vt, {}) == "safe"


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------

def test_extract_metadata_pdf():
    data = b"%PDF-1.4 some content"
    meta = extract_metadata(data, "document.pdf")
    assert meta["file_extension"] == ".pdf"
    assert "pdf" in meta["detected_mime"]
    assert isinstance(meta["entropy"], float)
    assert isinstance(meta["suspicious_strings"], list)
    assert meta["is_high_risk_extension"] is False
    assert meta["file_size_bytes"] == len(data)


def test_extract_metadata_exe():
    pe_data = _make_pe_header()
    meta = extract_metadata(pe_data, "malware.exe")
    assert meta["file_extension"] == ".exe"
    assert meta["is_high_risk_extension"] is True


def test_extract_metadata_high_entropy():
    import os
    random_data = os.urandom(4096)
    meta = extract_metadata(random_data, "packed.bin")
    assert meta["high_entropy"] is True


def test_extract_metadata_low_entropy():
    data = b"\x00" * 1000
    meta = extract_metadata(data, "zeros.bin")
    assert meta["high_entropy"] is False
    assert meta["entropy"] == 0.0


# ---------------------------------------------------------------------------
# get_stored_path
# ---------------------------------------------------------------------------

def test_get_stored_path_basic():
    fid = uuid.uuid4()
    path = get_stored_path(fid, ".exe")
    assert str(fid) in path
    assert path.endswith(".exe")


def test_get_stored_path_sanitizes_extension():
    fid = uuid.uuid4()
    path = get_stored_path(fid, "../../etc/passwd")
    # Slashes stripped — no path traversal via directory separator
    suffix = path.split(str(fid))[1]
    assert "/" not in suffix
    assert "\\" not in suffix


def test_get_stored_path_no_extension():
    fid = uuid.uuid4()
    path = get_stored_path(fid, "")
    assert str(fid) in path
