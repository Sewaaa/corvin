"""
Test suite per il modulo Reports.

- GET /reports/summary: JSON aggregato corretto e scope tenant
- GET /reports/pdf: PDF generato con content-type application/pdf
- Tenant isolation: org_A non vede dati di org_B
"""
import pytest


REGISTER_A = {
    "email": "report-ta@example.com",
    "password": "ReportTa1!",
    "full_name": "Report TA",
    "organization_name": "Report Tenant A",
}
REGISTER_B = {
    "email": "report-tb@example.com",
    "password": "ReportTb1!",
    "full_name": "Report TB",
    "organization_name": "Report Tenant B",
}


async def register_and_get_token(client, payload) -> str:
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /reports/summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_returns_all_modules(client):
    token = await register_and_get_token(client, REGISTER_A)
    resp = await client.get("/api/v1/reports/summary", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()

    # Verifica struttura di tutti i moduli
    assert "breach_monitor" in data
    assert "domain_reputation" in data
    assert "web_scanner" in data
    assert "email_protection" in data
    assert "file_sandbox" in data
    assert "notifications" in data
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_summary_breach_monitor_fields(client):
    token = await register_and_get_token(client, {
        "email": "report-bm@example.com",
        "password": "ReportBm1!",
        "full_name": "Report BM",
        "organization_name": "Report BM Org",
    })
    resp = await client.get("/api/v1/reports/summary", headers=auth_headers(token))
    bm = resp.json()["breach_monitor"]
    assert "monitored_emails" in bm
    assert "breached_emails" in bm
    assert "breach_rate_pct" in bm
    assert bm["monitored_emails"] >= 0
    assert 0.0 <= bm["breach_rate_pct"] <= 100.0


@pytest.mark.asyncio
async def test_summary_web_scanner_findings_by_severity(client):
    token = await register_and_get_token(client, {
        "email": "report-ws@example.com",
        "password": "ReportWs1!",
        "full_name": "Report WS",
        "organization_name": "Report WS Org",
    })
    resp = await client.get("/api/v1/reports/summary", headers=auth_headers(token))
    ws = resp.json()["web_scanner"]
    findings = ws["findings_by_severity"]
    for sev in ("critical", "high", "medium", "low", "info"):
        assert sev in findings
        assert findings[sev] >= 0


@pytest.mark.asyncio
async def test_summary_file_sandbox_by_status(client):
    token = await register_and_get_token(client, {
        "email": "report-sb@example.com",
        "password": "ReportSb1!",
        "full_name": "Report SB",
        "organization_name": "Report SB Org",
    })
    resp = await client.get("/api/v1/reports/summary", headers=auth_headers(token))
    sb = resp.json()["file_sandbox"]
    assert "total_files" in sb
    assert "by_status" in sb
    for st in ("safe", "suspicious", "malicious", "pending", "analyzing"):
        assert st in sb["by_status"]


# ---------------------------------------------------------------------------
# GET /reports/pdf
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_returns_pdf_content_type(client):
    token = await register_and_get_token(client, {
        "email": "report-pdf@example.com",
        "password": "ReportPdf1!",
        "full_name": "Report PDF",
        "organization_name": "Report PDF Org",
    })
    resp = await client.get("/api/v1/reports/pdf", headers=auth_headers(token))
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_pdf_has_pdf_magic_bytes(client):
    token = await register_and_get_token(client, {
        "email": "report-pdf2@example.com",
        "password": "ReportPdf2!",
        "full_name": "Report PDF2",
        "organization_name": "Report PDF2 Org",
    })
    resp = await client.get("/api/v1/reports/pdf", headers=auth_headers(token))
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_pdf_content_disposition_attachment(client):
    token = await register_and_get_token(client, {
        "email": "report-pdf3@example.com",
        "password": "ReportPdf3!",
        "full_name": "Report PDF3",
        "organization_name": "Report PDF3 Org",
    })
    resp = await client.get("/api/v1/reports/pdf", headers=auth_headers(token))
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".pdf" in cd


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_requires_auth(client):
    resp = await client.get("/api/v1/reports/summary")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_summary_counts_scoped_to_tenant(client, db_session):
    """org_B aggiunge dati — org_A non li vede nel summary."""
    token_a = await register_and_get_token(client, REGISTER_A)
    token_b = await register_and_get_token(client, REGISTER_B)

    # Aggiungi una email monitorata per org_B
    import uuid as _uuid
    from app.models.breach import MonitoredEmail
    user_b_resp = await client.get("/api/v1/auth/me", headers=auth_headers(token_b))
    org_b_id = _uuid.UUID(user_b_resp.json()["organization_id"])

    me = MonitoredEmail(
        organization_id=org_b_id,
        email_hash="a" * 64,
        email_masked="x***@example.com",
    )
    db_session.add(me)
    await db_session.commit()

    # org_A vede 0 email monitorate
    resp_a = await client.get("/api/v1/reports/summary", headers=auth_headers(token_a))
    assert resp_a.json()["breach_monitor"]["monitored_emails"] == 0

    # org_B vede 1 email monitorata
    resp_b = await client.get("/api/v1/reports/summary", headers=auth_headers(token_b))
    assert resp_b.json()["breach_monitor"]["monitored_emails"] >= 1
