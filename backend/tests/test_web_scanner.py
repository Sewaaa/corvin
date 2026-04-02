"""
Test suite per il Web Scanner module.

Strategia:
- Mock di httpx.AsyncClient per evitare chiamate di rete reali
- Test unitari per check_security_headers, check_exposed_files, detect_cms
- Test di integrazione per gli endpoint REST (start_scan, list, get, delete)
- Verifica tenant isolation
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.web_scanner.service import (
    check_security_headers,
    detect_cms,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER = {
    "email": "scanner-test@example.com",
    "password": "ScannerTest1!",
    "full_name": "Scanner Tester",
    "organization_name": "Scanner Test Org",
}


async def register_and_get_token(client, payload=None) -> str:
    p = payload or REGISTER
    resp = await client.post("/api/v1/auth/register", json=p)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def add_verified_domain(client, token: str, domain: str = "scan-target.com") -> str:
    """Aggiunge un dominio e lo marca come verificato bypassando il DNS."""
    resp = await client.post(
        "/api/v1/domain/",
        json={"domain": domain},
        headers=headers(token),
    )
    assert resp.status_code == 201

    domains = (await client.get("/api/v1/domain/", headers=headers(token))).json()
    domain_id = next(d["id"] for d in domains if d["domain"] == domain)

    with patch(
        "app.modules.domain_reputation.service.verify_domain_ownership",
        return_value=True,
    ):
        verify_resp = await client.post(
            f"/api/v1/domain/{domain_id}/verify",
            headers=headers(token),
        )
    assert verify_resp.status_code == 200
    return domain_id


# ---------------------------------------------------------------------------
# Unit test: check_security_headers
# ---------------------------------------------------------------------------

def _mock_response(headers_dict: dict, body: str = "") -> MagicMock:
    resp = MagicMock()
    resp.headers = headers_dict
    resp.text = body
    resp.status_code = 200
    return resp


def test_missing_hsts_generates_finding():
    resp = _mock_response({})  # nessun header
    findings = check_security_headers(resp)
    types = [f["type"] for f in findings]
    assert "missing_hsts" in types


def test_missing_csp_generates_finding():
    resp = _mock_response({})
    findings = check_security_headers(resp)
    types = [f["type"] for f in findings]
    assert "missing_csp" in types


def test_server_header_disclosure_generates_finding():
    resp = _mock_response({"server": "Apache/2.4.51 (Unix)"})
    findings = check_security_headers(resp)
    types = [f["type"] for f in findings]
    assert "server_header_disclosure" in types


def test_generic_server_header_no_finding():
    resp = _mock_response({"server": "cloudflare"})
    findings = check_security_headers(resp)
    types = [f["type"] for f in findings]
    assert "server_header_disclosure" not in types


def test_all_security_headers_present_no_findings():
    good_headers = {
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "permissions-policy": "geolocation=()",
    }
    resp = _mock_response(good_headers)
    findings = check_security_headers(resp)
    # Nessun finding di tipo "missing_*" o "server_header_disclosure"
    security_findings = [
        f for f in findings
        if f["type"] in (
            "missing_hsts", "missing_csp", "missing_x_frame_options",
            "missing_x_content_type_options", "missing_referrer_policy",
            "missing_permissions_policy", "server_header_disclosure",
            "x_powered_by_disclosure",
        )
    ]
    assert security_findings == []


# ---------------------------------------------------------------------------
# Unit test: detect_cms
# ---------------------------------------------------------------------------

def test_detect_wordpress():
    resp = _mock_response(
        {},
        body='<meta name="generator" content="WordPress 6.4.1">',
    )
    cms_name, version, findings = detect_cms(resp)
    assert cms_name == "WordPress"
    assert len(findings) >= 1


def test_detect_joomla():
    resp = _mock_response(
        {},
        body='<meta name="generator" content="Joomla! 4.3">',
    )
    cms_name, version, findings = detect_cms(resp)
    assert cms_name == "Joomla"


def test_detect_drupal():
    resp = _mock_response(
        {},
        body='<meta name="generator" content="Drupal 10">',
    )
    cms_name, version, findings = detect_cms(resp)
    assert cms_name == "Drupal"


def test_no_cms_returns_none():
    resp = _mock_response({}, body="<html><body>Custom site</body></html>")
    cms_name, version, findings = detect_cms(resp)
    assert cms_name is None
    assert findings == []


# ---------------------------------------------------------------------------
# Integration test: endpoint POST /web-scan/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_scan_unverified_domain_blocked(client):
    """Uno scan su dominio non verificato deve restituire 400."""
    token = await register_and_get_token(client)
    add_resp = await client.post(
        "/api/v1/domain/",
        json={"domain": "notverified-ws.com"},
        headers=headers(token),
    )
    assert add_resp.status_code == 201

    domains = (await client.get("/api/v1/domain/", headers=headers(token))).json()
    domain_id = next(d["id"] for d in domains if d["domain"] == "notverified-ws.com")

    resp = await client.post(
        "/api/v1/web-scan/",
        json={"domain_id": domain_id, "frequency": "manual"},
        headers=headers(token),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_start_scan_verified_domain_accepted(client):
    """Scan su dominio verificato deve tornare 202 e un record con status pending."""
    token = await register_and_get_token(client, {
        "email": "ws-accept@example.com",
        "password": "WsAccept1!",
        "full_name": "WS Accept",
        "organization_name": "WS Accept Org",
    })
    domain_id = await add_verified_domain(client, token, "ws-accept.com")

    with patch("app.modules.web_scanner.tasks.run_web_scan_task") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            "/api/v1/web-scan/",
            json={"domain_id": domain_id, "frequency": "manual"},
            headers=headers(token),
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "pending"
    assert data["domain_id"] == domain_id


@pytest.mark.asyncio
async def test_start_scan_unknown_domain_404(client):
    """domain_id inesistente deve restituire 404."""
    token = await register_and_get_token(client, {
        "email": "ws-404@example.com",
        "password": "Ws404Test1!",
        "full_name": "WS 404",
        "organization_name": "WS 404 Org",
    })
    import uuid
    resp = await client.post(
        "/api/v1/web-scan/",
        json={"domain_id": str(uuid.uuid4()), "frequency": "manual"},
        headers=headers(token),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration test: GET /web-scan/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_scans_initially_empty(client):
    token = await register_and_get_token(client, {
        "email": "ws-list@example.com",
        "password": "WsList1!",
        "full_name": "WS List",
        "organization_name": "WS List Org",
    })
    resp = await client.get("/api/v1/web-scan/", headers=headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_scans_shows_created_scan(client):
    token = await register_and_get_token(client, {
        "email": "ws-list2@example.com",
        "password": "WsList2!X",
        "full_name": "WS List2",
        "organization_name": "WS List2 Org",
    })
    domain_id = await add_verified_domain(client, token, "ws-list2.com")

    with patch("app.modules.web_scanner.tasks.run_web_scan_task") as mock_task:
        mock_task.delay = MagicMock()
        await client.post(
            "/api/v1/web-scan/",
            json={"domain_id": domain_id, "frequency": "manual"},
            headers=headers(token),
        )

    resp = await client.get("/api/v1/web-scan/", headers=headers(token))
    assert resp.status_code == 200
    scans = resp.json()
    assert len(scans) >= 1
    assert any(s["domain_id"] == domain_id for s in scans)


# ---------------------------------------------------------------------------
# Integration test: GET /web-scan/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_scan_detail(client):
    token = await register_and_get_token(client, {
        "email": "ws-detail@example.com",
        "password": "WsDetail1!",
        "full_name": "WS Detail",
        "organization_name": "WS Detail Org",
    })
    domain_id = await add_verified_domain(client, token, "ws-detail.com")

    with patch("app.modules.web_scanner.tasks.run_web_scan_task") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await client.post(
            "/api/v1/web-scan/",
            json={"domain_id": domain_id, "frequency": "manual"},
            headers=headers(token),
        )
    scan_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/web-scan/{scan_id}", headers=headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == scan_id
    assert "findings" in data
    assert "summary" in data


@pytest.mark.asyncio
async def test_get_scan_not_found(client):
    token = await register_and_get_token(client, {
        "email": "ws-nf@example.com",
        "password": "WsNf1!Test",
        "full_name": "WS NF",
        "organization_name": "WS NF Org",
    })
    import uuid
    resp = await client.get(f"/api/v1/web-scan/{uuid.uuid4()}", headers=headers(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration test: DELETE /web-scan/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_scan_as_admin(client):
    token = await register_and_get_token(client, {
        "email": "ws-del@example.com",
        "password": "WsDel1!Test",
        "full_name": "WS Del",
        "organization_name": "WS Del Org",
    })
    domain_id = await add_verified_domain(client, token, "ws-del.com")

    with patch("app.modules.web_scanner.tasks.run_web_scan_task") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await client.post(
            "/api/v1/web-scan/",
            json={"domain_id": domain_id, "frequency": "manual"},
            headers=headers(token),
        )
    scan_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/web-scan/{scan_id}", headers=headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/web-scan/{scan_id}", headers=headers(token))
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_scan_access_404(client):
    """org_A non può leggere gli scan di org_B."""
    token_a = await register_and_get_token(client, {
        "email": "ws-ta@example.com",
        "password": "WsTa1!Pass",
        "full_name": "WS TA",
        "organization_name": "WS Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "ws-tb@example.com",
        "password": "WsTb1!Pass",
        "full_name": "WS TB",
        "organization_name": "WS Tenant B",
    })

    domain_id = await add_verified_domain(client, token_b, "ws-tb-only.com")

    with patch("app.modules.web_scanner.tasks.run_web_scan_task") as mock_task:
        mock_task.delay = MagicMock()
        create_resp = await client.post(
            "/api/v1/web-scan/",
            json={"domain_id": domain_id, "frequency": "manual"},
            headers=headers(token_b),
        )
    scan_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/web-scan/{scan_id}", headers=headers(token_a))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_scan_list_isolated(client):
    """Gli scan di org_B non appaiono nella lista di org_A."""
    token_a = await register_and_get_token(client, {
        "email": "ws-list-ta@example.com",
        "password": "WsListTa1!",
        "full_name": "WS List TA",
        "organization_name": "WS List Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "ws-list-tb@example.com",
        "password": "WsListTb1!",
        "full_name": "WS List TB",
        "organization_name": "WS List Tenant B",
    })

    domain_id = await add_verified_domain(client, token_b, "ws-list-tb.com")

    with patch("app.modules.web_scanner.tasks.run_web_scan_task") as mock_task:
        mock_task.delay = MagicMock()
        await client.post(
            "/api/v1/web-scan/",
            json={"domain_id": domain_id, "frequency": "manual"},
            headers=headers(token_b),
        )

    resp_a = await client.get("/api/v1/web-scan/", headers=headers(token_a))
    assert resp_a.status_code == 200
    scan_ids_a = {s["id"] for s in resp_a.json()}

    resp_b = await client.get("/api/v1/web-scan/", headers=headers(token_b))
    scan_ids_b = {s["id"] for s in resp_b.json()}

    assert scan_ids_a.isdisjoint(scan_ids_b)
