"""
Test suite per il modulo Sandbox (analisi statica file).

Strategia:
- Unit test: hash, entropy, YARA, verdict, PE detection
- Integration test: upload, list, detail, delete — con mock Celery e FS
- Tenant isolation
"""
import io
import struct
from unittest.mock import MagicMock, patch

import pytest

from app.modules.sandbox.service import (
    calculate_verdict,
    check_pe_characteristics,
    compute_entropy,
    compute_hashes,
    extract_suspicious_strings,
    run_yara_scan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER = {
    "email": "sandbox-test@example.com",
    "password": "SandboxTest1!",
    "full_name": "Sandbox Tester",
    "organization_name": "Sandbox Test Org",
}


async def register_and_get_token(client, payload=None) -> str:
    p = payload or REGISTER
    resp = await client.post("/api/v1/auth/register", json=p)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _text_file(content: str = "Hello, world!") -> tuple:
    data = content.encode()
    return ("test.txt", io.BytesIO(data), "text/plain")


def _exe_file() -> tuple:
    """File con header MZ (PE stub minimale)."""
    header = b"MZ" + b"\x00" * 58 + struct.pack("<I", 64) + b"PE\x00\x00" + b"\x00" * 20
    return ("evil.exe", io.BytesIO(header), "application/x-dosexec")


# ---------------------------------------------------------------------------
# Unit test: compute_hashes
# ---------------------------------------------------------------------------

def test_compute_hashes_deterministic():
    data = b"corvin test data"
    md5_1, sha256_1 = compute_hashes(data)
    md5_2, sha256_2 = compute_hashes(data)
    assert md5_1 == md5_2
    assert sha256_1 == sha256_2
    assert len(sha256_1) == 64
    assert len(md5_1) == 32


def test_compute_hashes_known_value():
    import hashlib
    data = b"hello"
    _, sha256 = compute_hashes(data)
    expected = hashlib.sha256(b"hello").hexdigest()
    assert sha256 == expected


# ---------------------------------------------------------------------------
# Unit test: entropy
# ---------------------------------------------------------------------------

def test_entropy_uniform_bytes_high():
    # Dati pseudo-casuali → alta entropia
    import os
    data = os.urandom(1024)
    e = compute_entropy(data)
    assert e > 6.0


def test_entropy_repeated_byte_low():
    # Tutti lo stesso byte → entropia 0
    data = b"\x00" * 1024
    e = compute_entropy(data)
    assert e == 0.0


def test_entropy_text_medium():
    data = b"The quick brown fox jumps over the lazy dog" * 10
    e = compute_entropy(data)
    assert 3.0 < e < 6.0


# ---------------------------------------------------------------------------
# Unit test: YARA scan
# ---------------------------------------------------------------------------

def test_yara_pe_header_detected():
    data = b"MZ" + b"\x00" * 58 + struct.pack("<I", 64) + b"PE\x00\x00" + b"\x00" * 100
    matches = run_yara_scan(data)
    rule_names = [m["rule"] for m in matches]
    assert "PE_Executable" in rule_names


def test_yara_elf_header_detected():
    data = b"\x7fELF" + b"\x00" * 100
    matches = run_yara_scan(data)
    rule_names = [m["rule"] for m in matches]
    assert "ELF_Executable" in rule_names


def test_yara_macro_detected():
    data = b"VBA AutoOpen Shell( " + b"\x00" * 20
    matches = run_yara_scan(data)
    rule_names = [m["rule"] for m in matches]
    assert "Office_Macro_Indicator" in rule_names


def test_yara_php_webshell_detected():
    data = b"<?php eval(base64_decode($_POST['cmd'])); ?>"
    matches = run_yara_scan(data)
    rule_names = [m["rule"] for m in matches]
    assert "Webshell_PHP" in rule_names


def test_yara_clean_file_no_match():
    data = b"Hello, this is a perfectly normal text document with nothing suspicious."
    matches = run_yara_scan(data)
    assert matches == []


# ---------------------------------------------------------------------------
# Unit test: verdict
# ---------------------------------------------------------------------------

def test_verdict_safe():
    result = calculate_verdict([], None, {"high_entropy": False, "is_high_risk_extension": False, "suspicious_strings": []})
    assert result == "safe"


def test_verdict_malicious_vt():
    vt = {"malicious": 10, "detections": 10, "total": 70}
    result = calculate_verdict([], vt, {})
    assert result == "malicious"


def test_verdict_malicious_yara_critical():
    yara = [{"rule": "Webshell_PHP", "severity": "critical", "category": "webshell"}]
    result = calculate_verdict(yara, None, {})
    assert result == "malicious"


def test_verdict_suspicious_yara_high():
    yara = [{"rule": "Suspicious_PowerShell", "severity": "high", "category": "powershell"}]
    result = calculate_verdict(yara, None, {})
    assert result == "suspicious"


def test_verdict_suspicious_high_entropy_risky_ext():
    result = calculate_verdict([], None, {
        "high_entropy": True,
        "is_high_risk_extension": True,
        "suspicious_strings": [],
    })
    assert result == "suspicious"


def test_verdict_vt_not_found_still_safe():
    vt = {"status": "not_found", "detections": 0, "total": 0}
    result = calculate_verdict([], vt, {
        "high_entropy": False,
        "is_high_risk_extension": False,
        "suspicious_strings": [],
    })
    assert result == "safe"


# ---------------------------------------------------------------------------
# Unit test: PE detection
# ---------------------------------------------------------------------------

def test_pe_characteristics_valid():
    header = b"MZ" + b"\x00" * 58 + struct.pack("<I", 64)
    pe_sig = b"PE\x00\x00"
    machine = struct.pack("<H", 0x8664)  # x64
    rest = struct.pack("<H", 3) + b"\x00" * 12 + struct.pack("<H", 0x0002)
    data = header + pe_sig + machine + rest + b"\x00" * 200
    result = check_pe_characteristics(data)
    assert result is not None
    assert result["architecture"] == "x64"
    assert result["num_sections"] == 3


def test_pe_characteristics_non_pe():
    result = check_pe_characteristics(b"%PDF-1.4 some content here")
    assert result is None


# ---------------------------------------------------------------------------
# Unit test: extract_suspicious_strings
# ---------------------------------------------------------------------------

def test_extract_powershell_string():
    data = b"cmd.exe /c powershell -enc SGVsbG8="
    found = extract_suspicious_strings(data)
    assert any("powershell" in s.lower() or "cmd" in s.lower() for s in found)


def test_extract_no_strings_clean():
    data = b"This is a clean text document with no suspicious content at all."
    found = extract_suspicious_strings(data)
    assert len(found) == 0


# ---------------------------------------------------------------------------
# Integration test: POST /sandbox/upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upload_text_file_accepted(client, tmp_path):
    token = await register_and_get_token(client)

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("readme.txt", io.BytesIO(b"Hello world"), "text/plain")},
            headers=auth_headers(token),
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["original_filename"] == "readme.txt"
    assert data["status"] == "pending"
    assert "sha256_hash" in data


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(client, tmp_path):
    token = await register_and_get_token(client, {
        "email": "sb-empty@example.com",
        "password": "SbEmpty1!",
        "full_name": "SB Empty",
        "organization_name": "SB Empty Org",
    })
    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)):
        resp = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
            headers=auth_headers(token),
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_oversized_file_rejected(client, tmp_path):
    token = await register_and_get_token(client, {
        "email": "sb-big@example.com",
        "password": "SbBig1!Xx",
        "full_name": "SB Big",
        "organization_name": "SB Big Org",
    })
    # 11 MB > default 10 MB limit
    big_data = b"A" * (11 * 1024 * 1024)
    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)):
        resp = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("big.bin", io.BytesIO(big_data), "application/octet-stream")},
            headers=auth_headers(token),
        )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_upload_duplicate_returns_existing(client, tmp_path):
    """Lo stesso hash SHA256 non deve creare un secondo record."""
    token = await register_and_get_token(client, {
        "email": "sb-dup@example.com",
        "password": "SbDup1!Xx",
        "full_name": "SB Dup",
        "organization_name": "SB Dup Org",
    })
    content = b"identical file content"

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        r1 = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("file1.txt", io.BytesIO(content), "text/plain")},
            headers=auth_headers(token),
        )
        r2 = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("file2.txt", io.BytesIO(content), "text/plain")},
            headers=auth_headers(token),
        )

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["id"] == r2.json()["id"]


# ---------------------------------------------------------------------------
# Integration test: GET /sandbox/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_files_initially_empty(client):
    token = await register_and_get_token(client, {
        "email": "sb-list@example.com",
        "password": "SbList1!X",
        "full_name": "SB List",
        "organization_name": "SB List Org",
    })
    resp = await client.get("/api/v1/sandbox/", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_shows_uploaded_file(client, tmp_path):
    token = await register_and_get_token(client, {
        "email": "sb-list2@example.com",
        "password": "SbList2!X",
        "full_name": "SB List2",
        "organization_name": "SB List2 Org",
    })

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("hello.txt", io.BytesIO(b"hello"), "text/plain")},
            headers=auth_headers(token),
        )

    resp = await client.get("/api/v1/sandbox/", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["original_filename"] == "hello.txt"


# ---------------------------------------------------------------------------
# Integration test: GET + DELETE /sandbox/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_file_detail(client, tmp_path):
    token = await register_and_get_token(client, {
        "email": "sb-detail@example.com",
        "password": "SbDetail1!",
        "full_name": "SB Detail",
        "organization_name": "SB Detail Org",
    })

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        up = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("test.txt", io.BytesIO(b"details"), "text/plain")},
            headers=auth_headers(token),
        )
    file_id = up.json()["id"]

    resp = await client.get(f"/api/v1/sandbox/{file_id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == file_id


@pytest.mark.asyncio
async def test_get_file_not_found(client):
    token = await register_and_get_token(client, {
        "email": "sb-404@example.com",
        "password": "Sb404Test1!",
        "full_name": "SB 404",
        "organization_name": "SB 404 Org",
    })
    import uuid
    resp = await client.get(f"/api/v1/sandbox/{uuid.uuid4()}", headers=auth_headers(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_file(client, tmp_path):
    token = await register_and_get_token(client, {
        "email": "sb-del@example.com",
        "password": "SbDel1!Test",
        "full_name": "SB Del",
        "organization_name": "SB Del Org",
    })

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        up = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("todelete.txt", io.BytesIO(b"bye"), "text/plain")},
            headers=auth_headers(token),
        )
    file_id = up.json()["id"]

    del_resp = await client.delete(f"/api/v1/sandbox/{file_id}", headers=auth_headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/sandbox/{file_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_file_access_404(client, tmp_path):
    token_a = await register_and_get_token(client, {
        "email": "sb-ta@example.com",
        "password": "SbTa1!Pass",
        "full_name": "SB TA",
        "organization_name": "SB Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "sb-tb@example.com",
        "password": "SbTb1!Pass",
        "full_name": "SB TB",
        "organization_name": "SB Tenant B",
    })

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        up_b = await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("secret_b.txt", io.BytesIO(b"secret"), "text/plain")},
            headers=auth_headers(token_b),
        )
    file_id_b = up_b.json()["id"]

    resp = await client.get(f"/api/v1/sandbox/{file_id_b}", headers=auth_headers(token_a))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_file_list_scoped_to_tenant(client, tmp_path):
    token_a = await register_and_get_token(client, {
        "email": "sb-list-ta@example.com",
        "password": "SbListTa1!",
        "full_name": "SB List TA",
        "organization_name": "SB List Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "sb-list-tb@example.com",
        "password": "SbListTb1!",
        "full_name": "SB List TB",
        "organization_name": "SB List Tenant B",
    })

    with patch("app.modules.sandbox.service.UPLOAD_DIR", str(tmp_path)), \
         patch("app.modules.sandbox.tasks.analyze_file_task") as mock_task:
        mock_task.delay = MagicMock()
        await client.post(
            "/api/v1/sandbox/upload",
            files={"file": ("only_b.txt", io.BytesIO(b"only b"), "text/plain")},
            headers=auth_headers(token_b),
        )

    list_a = await client.get("/api/v1/sandbox/", headers=auth_headers(token_a))
    list_b = await client.get("/api/v1/sandbox/", headers=auth_headers(token_b))

    ids_a = {f["id"] for f in list_a.json()}
    ids_b = {f["id"] for f in list_b.json()}
    assert ids_a.isdisjoint(ids_b)
