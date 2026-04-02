"""
Test suite per il Domain Reputation module.

Strategia: mock delle chiamate DNS, SSL e WHOIS per evitare dipendenze di rete.
Verifica: scoring, finding generation, tenant isolation, ownership verification.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.domain_reputation.service import (
    VERIFICATION_PREFIX,
    calculate_reputation_score,
    check_dns_records,
    generate_verification_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER = {
    "email": "domain-test@example.com",
    "password": "DomainTest1!",
    "full_name": "Domain Tester",
    "organization_name": "Domain Test Org",
}


async def register_and_get_token(client, payload=None) -> str:
    p = payload or REGISTER
    resp = await client.post("/api/v1/auth/register", json=p)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit test: utilità
# ---------------------------------------------------------------------------

def test_generate_verification_token_has_prefix():
    token = generate_verification_token()
    assert token.startswith(VERIFICATION_PREFIX)
    assert len(token) > len(VERIFICATION_PREFIX) + 10


def test_generate_verification_tokens_are_unique():
    tokens = {generate_verification_token() for _ in range(20)}
    assert len(tokens) == 20


def test_reputation_score_perfect_no_findings():
    assert calculate_reputation_score([]) == 100


def test_reputation_score_critical_deducts_30():
    findings = [{"severity": "critical", "title": "Something bad"}]
    assert calculate_reputation_score(findings) == 70


def test_reputation_score_multiple_findings():
    findings = [
        {"severity": "critical"},  # -30
        {"severity": "high"},      # -15
        {"severity": "medium"},    # -8
    ]
    assert calculate_reputation_score(findings) == 47


def test_reputation_score_minimum_is_zero():
    findings = [{"severity": "critical"}] * 10  # 10 * 30 = 300 deductions
    assert calculate_reputation_score(findings) == 0


# ---------------------------------------------------------------------------
# Unit test: DNS check (mock del resolver)
# ---------------------------------------------------------------------------

def test_dns_check_detects_missing_spf():
    """Dominio senza record SPF deve generare finding high."""
    with patch("app.modules.domain_reputation.service._resolve_safe") as mock_resolve:
        def side_effect(domain, record_type, **kwargs):
            if record_type == "TXT":
                return ["v=DMARC1; p=reject;"]  # DMARC sì, SPF no
            if record_type == "MX":
                return ["10 mail.example.com."]
            return []
        mock_resolve.side_effect = side_effect

        result = check_dns_records("example.com")

    finding_types = [f["type"] for f in result["findings"]]
    assert "no_spf_record" in finding_types


def test_dns_check_detects_missing_dmarc():
    """Dominio senza DMARC deve generare finding high."""
    with patch("app.modules.domain_reputation.service._resolve_safe") as mock_resolve:
        def side_effect(domain, record_type, **kwargs):
            if record_type == "TXT" and not domain.startswith("_dmarc"):
                return ["v=spf1 include:_spf.google.com ~all"]
            return []
        mock_resolve.side_effect = side_effect

        result = check_dns_records("example.com")

    finding_types = [f["type"] for f in result["findings"]]
    assert "no_dmarc_record" in finding_types


def test_dns_check_dmarc_none_policy_is_medium():
    """DMARC p=none deve generare un finding medium (non blocca spoofing)."""
    with patch("app.modules.domain_reputation.service._resolve_safe") as mock_resolve:
        def side_effect(domain, record_type, **kwargs):
            if record_type == "TXT" and domain.startswith("_dmarc"):
                return ["v=DMARC1; p=none; rua=mailto:report@example.com"]
            if record_type == "TXT":
                return ["v=spf1 -all"]
            if record_type == "MX":
                return ["10 mail.example.com."]
            return []
        mock_resolve.side_effect = side_effect

        result = check_dns_records("example.com")

    finding_types = [f["type"] for f in result["findings"]]
    assert "dmarc_policy_none" in finding_types
    severity = next(f["severity"] for f in result["findings"] if f["type"] == "dmarc_policy_none")
    assert severity == "medium"


def test_dns_check_clean_domain_no_findings():
    """Dominio con SPF, DMARC reject e MX non deve generare finding."""
    with patch("app.modules.domain_reputation.service._resolve_safe") as mock_resolve:
        def side_effect(domain, record_type, **kwargs):
            if record_type == "TXT" and domain.startswith("_dmarc"):
                return ["v=DMARC1; p=reject;"]
            if record_type == "TXT":
                return ["v=spf1 -all"]
            if record_type == "MX":
                return ["10 mail.example.com."]
            return []
        mock_resolve.side_effect = side_effect

        result = check_dns_records("example.com")

    assert result["findings"] == []


# ---------------------------------------------------------------------------
# Test endpoint: aggiunta dominio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_domain_returns_verification_token(client):
    token = await register_and_get_token(client)
    resp = await client.post(
        "/api/v1/domain/",
        json={"domain": "example.com"},
        headers=headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["domain"] == "example.com"
    assert VERIFICATION_PREFIX in data["verification_token"]
    assert "instructions" in data


@pytest.mark.asyncio
async def test_add_duplicate_domain_conflict(client):
    token = await register_and_get_token(client)
    await client.post("/api/v1/domain/", json={"domain": "dup.com"}, headers=headers(token))
    resp = await client.post("/api/v1/domain/", json={"domain": "dup.com"}, headers=headers(token))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_invalid_domain_rejected(client):
    token = await register_and_get_token(client)
    resp = await client.post(
        "/api/v1/domain/",
        json={"domain": "not a domain!!"},
        headers=headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_domains_is_empty_initially(client):
    token = await register_and_get_token(client)
    resp = await client.get("/api/v1/domain/", headers=headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_domains_shows_added_domain(client):
    token = await register_and_get_token(client)
    await client.post("/api/v1/domain/", json={"domain": "listed.com"}, headers=headers(token))
    resp = await client.get("/api/v1/domain/", headers=headers(token))
    assert any(d["domain"] == "listed.com" for d in resp.json())


# ---------------------------------------------------------------------------
# Test: verifica ownership
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_domain_fails_without_txt_record(client):
    """Senza il record TXT nel DNS, la verifica deve fallire con 400."""
    token = await register_and_get_token(client)
    add_resp = await client.post(
        "/api/v1/domain/", json={"domain": "unverified.com"}, headers=headers(token)
    )
    # Recupera l'id dal dominio appena aggiunto
    domains_resp = await client.get("/api/v1/domain/", headers=headers(token))
    domain_id = domains_resp.json()[0]["id"]

    with patch(
        "app.modules.domain_reputation.service.verify_domain_ownership",
        return_value=False,
    ):
        resp = await client.post(f"/api/v1/domain/{domain_id}/verify", headers=headers(token))

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_scan_unverified_domain_blocked(client):
    """Tentare uno scan su un dominio non verificato deve restituire 400."""
    token = await register_and_get_token(client)
    await client.post("/api/v1/domain/", json={"domain": "noscan.com"}, headers=headers(token))
    domains = (await client.get("/api/v1/domain/", headers=headers(token))).json()
    domain_id = domains[0]["id"]

    resp = await client.post(f"/api/v1/domain/{domain_id}/scan", headers=headers(token))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test: tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_domain_list_scoped_to_tenant(client):
    """I domini di org_A non devono essere visibili da org_B."""
    token_a = await register_and_get_token(client)
    token_b = await register_and_get_token(client, {
        "email": "orgb-domain@example.com",
        "password": "OrgBPass1!",
        "full_name": "Org B",
        "organization_name": "Org B Domain",
    })

    await client.post("/api/v1/domain/", json={"domain": "secret-a.com"}, headers=headers(token_a))

    resp_b = await client.get("/api/v1/domain/", headers=headers(token_b))
    assert resp_b.status_code == 200
    assert all(d["domain"] != "secret-a.com" for d in resp_b.json())


@pytest.mark.asyncio
async def test_cross_tenant_domain_access_returns_404(client):
    """org_A non può accedere ai dettagli di un dominio di org_B."""
    token_a = await register_and_get_token(client)
    token_b = await register_and_get_token(client, {
        "email": "orgb2-domain@example.com",
        "password": "OrgB2Pass1!",
        "full_name": "Org B2",
        "organization_name": "Org B2 Domain",
    })

    await client.post("/api/v1/domain/", json={"domain": "only-b.com"}, headers=headers(token_b))
    domains_b = (await client.get("/api/v1/domain/", headers=headers(token_b))).json()
    domain_id = domains_b[0]["id"]

    resp = await client.get(f"/api/v1/domain/{domain_id}", headers=headers(token_a))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_domain_delete_returns_404(client):
    """org_A non può eliminare un dominio di org_B."""
    token_a = await register_and_get_token(client)
    token_b = await register_and_get_token(client, {
        "email": "orgb3-domain@example.com",
        "password": "OrgB3Pass1!",
        "full_name": "Org B3",
        "organization_name": "Org B3 Domain",
    })

    await client.post("/api/v1/domain/", json={"domain": "delete-b.com"}, headers=headers(token_b))
    domains_b = (await client.get("/api/v1/domain/", headers=headers(token_b))).json()
    domain_id = domains_b[0]["id"]

    resp = await client.delete(f"/api/v1/domain/{domain_id}", headers=headers(token_a))
    assert resp.status_code == 404
