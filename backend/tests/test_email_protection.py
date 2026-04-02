"""
Test suite per il modulo Email Protection.

Strategia:
- Unit test: encryption, analisi header phishing, lookalike detection
- Integration test: endpoint REST (accounts, threats) con mock IMAP
- Tenant isolation
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.email_protection.service import (
    analyze_email_headers,
    decrypt_password,
    encrypt_password,
    _levenshtein,
    _is_lookalike_domain,
    _extract_email_address,
    _parse_auth_results,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER = {
    "email": "email-test@example.com",
    "password": "EmailTest1!",
    "full_name": "Email Tester",
    "organization_name": "Email Test Org",
}


async def register_and_get_token(client, payload=None) -> str:
    p = payload or REGISTER
    resp = await client.post("/api/v1/auth/register", json=p)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _clean_email_data(**overrides) -> dict:
    """Restituisce un email_data pulito (nessun indicatore di phishing)."""
    base = {
        "from": "noreply@trusted.com",
        "reply_to": "",
        "subject": "Hello, your monthly invoice",
        "authentication_results": "mx.trusted.com; spf=pass dkim=pass dmarc=pass",
        "dkim_signature": "v=1; ...",
        "x_spam_status": "No",
        "message_id": "<abc123@trusted.com>",
        "to": "user@example.com",
        "date": "",
        "received": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Unit test: encryption
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    password = "super_secret_imap_password!"
    encrypted = encrypt_password(password)
    assert encrypted != password
    assert decrypt_password(encrypted) == password


def test_encrypt_produces_different_ciphertexts():
    """Fernet usa un nonce casuale — lo stesso plaintext produce ciphertext diversi."""
    p = "mypassword"
    c1 = encrypt_password(p)
    c2 = encrypt_password(p)
    assert c1 != c2
    assert decrypt_password(c1) == p
    assert decrypt_password(c2) == p


# ---------------------------------------------------------------------------
# Unit test: utility functions
# ---------------------------------------------------------------------------

def test_levenshtein_identical():
    assert _levenshtein("paypal", "paypal") == 0


def test_levenshtein_one_insertion():
    assert _levenshtein("paypal", "paypa1") == 1


def test_levenshtein_very_different():
    assert _levenshtein("paypal", "google") > 4


def test_extract_email_address_with_display_name():
    addr = _extract_email_address("John Doe <john@example.com>")
    assert addr == "john@example.com"


def test_extract_email_address_bare():
    addr = _extract_email_address("john@example.com")
    assert addr == "john@example.com"


def test_is_lookalike_paypa1():
    result = _is_lookalike_domain("paypa1.com", ["paypal", "google"])
    assert result == "paypal"


def test_is_lookalike_exact_match_not_flagged():
    result = _is_lookalike_domain("paypal.com", ["paypal"])
    assert result is None


def test_is_lookalike_very_different_not_flagged():
    result = _is_lookalike_domain("randomsite.com", ["paypal", "google"])
    assert result is None


def test_parse_auth_results_all_pass():
    header = "mx.example.com; spf=pass dkim=pass dmarc=pass"
    r = _parse_auth_results(header)
    assert r["spf"] == "pass"
    assert r["dkim"] == "pass"
    assert r["dmarc"] == "pass"


def test_parse_auth_results_fail():
    header = "mx.example.com; spf=fail dkim=fail dmarc=fail"
    r = _parse_auth_results(header)
    assert r["spf"] == "fail"
    assert r["dmarc"] == "fail"


def test_parse_auth_results_empty():
    r = _parse_auth_results("")
    assert r == {"spf": "none", "dkim": "none", "dmarc": "none"}


# ---------------------------------------------------------------------------
# Unit test: analyze_email_headers
# ---------------------------------------------------------------------------

def test_clean_email_returns_none():
    data = _clean_email_data()
    result = analyze_email_headers(data)
    assert result is None


def test_spf_fail_generates_finding():
    data = _clean_email_data(
        authentication_results="mx.example.com; spf=fail dkim=pass dmarc=pass"
    )
    result = analyze_email_headers(data)
    assert result is not None
    types = [r["type"] for r in result["detection_reasons"]]
    assert "spf_fail" in types


def test_dmarc_fail_is_critical():
    data = _clean_email_data(
        authentication_results="mx.example.com; spf=fail dkim=fail dmarc=fail"
    )
    result = analyze_email_headers(data)
    assert result is not None
    assert result["severity"] in ("critical", "high")
    types = [r["type"] for r in result["detection_reasons"]]
    assert "dmarc_fail" in types


def test_reply_to_mismatch_detected():
    data = _clean_email_data(
        **{
            "from": "ceo@legit-company.com",
            "reply_to": "hacker@evil-domain.ru",
            "authentication_results": "mx.legit.com; spf=pass dkim=pass dmarc=pass",
        }
    )
    result = analyze_email_headers(data)
    assert result is not None
    types = [r["type"] for r in result["detection_reasons"]]
    assert "reply_to_mismatch" in types


def test_display_name_spoofing_paypal():
    data = _clean_email_data(
        **{
            "from": "PayPal Security <noreply@paypa1-security.com>",
            "authentication_results": "mx.evil.com; spf=pass dkim=pass dmarc=pass",
        }
    )
    result = analyze_email_headers(data)
    assert result is not None
    types = [r["type"] for r in result["detection_reasons"]]
    assert "display_name_spoofing" in types or "lookalike_domain" in types


def test_lookalike_domain_detected():
    data = _clean_email_data(
        **{
            "from": "support@paypa1.com",
            "authentication_results": "mx.paypa1.com; spf=pass dkim=pass dmarc=pass",
        }
    )
    result = analyze_email_headers(data)
    assert result is not None
    types = [r["type"] for r in result["detection_reasons"]]
    assert "lookalike_domain" in types


def test_urgency_keywords_detected():
    data = _clean_email_data(
        subject="URGENT: your account has been suspended",
        authentication_results="mx.legit.com; spf=pass dkim=pass dmarc=pass",
    )
    result = analyze_email_headers(data)
    assert result is not None
    types = [r["type"] for r in result["detection_reasons"]]
    assert "urgency_keywords" in types


def test_threat_type_impersonation():
    data = _clean_email_data(
        **{
            "from": "Amazon Security <noreply@amaz0n-alert.com>",
            "authentication_results": "mx.evil.com; spf=pass dkim=pass dmarc=pass",
        }
    )
    result = analyze_email_headers(data)
    if result:
        assert result["threat_type"] in ("impersonation", "phishing", "suspicious", "spoofing")


def test_confidence_score_format():
    data = _clean_email_data(
        authentication_results="mx.evil.com; spf=fail dkim=fail dmarc=fail"
    )
    result = analyze_email_headers(data)
    assert result is not None
    assert result["confidence_score"].endswith("%")


# ---------------------------------------------------------------------------
# Integration test: POST /email/accounts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_account_imap_failure_returns_400(client):
    """Se IMAP non risponde, deve restituire 400."""
    token = await register_and_get_token(client)

    with patch(
        "app.modules.email_protection.service.test_imap_connection",
        return_value=False,
    ):
        resp = await client.post(
            "/api/v1/email/accounts",
            json={
                "email_address": "test@example.com",
                "imap_host": "imap.example.com",
                "imap_port": 993,
                "password": "secret",
                "use_ssl": True,
            },
            headers=headers(token),
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_add_account_success(client):
    """Connessione IMAP OK → account salvato con 201."""
    token = await register_and_get_token(client, {
        "email": "email-add@example.com",
        "password": "EmailAdd1!",
        "full_name": "Email Add",
        "organization_name": "Email Add Org",
    })

    with patch(
        "app.modules.email_protection.service.test_imap_connection",
        return_value=True,
    ):
        resp = await client.post(
            "/api/v1/email/accounts",
            json={
                "email_address": "monitored@company.com",
                "imap_host": "imap.company.com",
                "imap_port": 993,
                "password": "imap_secret",
                "use_ssl": True,
            },
            headers=headers(token),
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email_address"] == "monitored@company.com"
    assert "password" not in data  # password non esposta
    assert "encrypted_password" not in data


@pytest.mark.asyncio
async def test_add_duplicate_account_409(client):
    token = await register_and_get_token(client, {
        "email": "email-dup@example.com",
        "password": "EmailDup1!",
        "full_name": "Email Dup",
        "organization_name": "Email Dup Org",
    })

    payload = {
        "email_address": "dup@company.com",
        "imap_host": "imap.company.com",
        "imap_port": 993,
        "password": "secret",
        "use_ssl": True,
    }

    with patch("app.modules.email_protection.service.test_imap_connection", return_value=True):
        await client.post("/api/v1/email/accounts", json=payload, headers=headers(token))
        resp = await client.post("/api/v1/email/accounts", json=payload, headers=headers(token))

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_accounts_empty(client):
    token = await register_and_get_token(client, {
        "email": "email-empty@example.com",
        "password": "EmailEmpty1!",
        "full_name": "Email Empty",
        "organization_name": "Email Empty Org",
    })
    resp = await client.get("/api/v1/email/accounts", headers=headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_delete_account(client):
    token = await register_and_get_token(client, {
        "email": "email-del@example.com",
        "password": "EmailDel1!",
        "full_name": "Email Del",
        "organization_name": "Email Del Org",
    })

    with patch("app.modules.email_protection.service.test_imap_connection", return_value=True):
        create_resp = await client.post(
            "/api/v1/email/accounts",
            json={
                "email_address": "todelete@company.com",
                "imap_host": "imap.company.com",
                "imap_port": 993,
                "password": "s3cret",
                "use_ssl": True,
            },
            headers=headers(token),
        )
    account_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/email/accounts/{account_id}", headers=headers(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/email/accounts/{account_id}", headers=headers(token))
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration test: GET /email/threats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_threats_empty(client):
    token = await register_and_get_token(client, {
        "email": "email-thr@example.com",
        "password": "EmailThr1!",
        "full_name": "Email Thr",
        "organization_name": "Email Thr Org",
    })
    resp = await client.get("/api/v1/email/threats", headers=headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_account_access_404(client):
    """org_A non può vedere gli account di org_B."""
    token_a = await register_and_get_token(client, {
        "email": "email-ta@example.com",
        "password": "EmailTa1!",
        "full_name": "Email TA",
        "organization_name": "Email Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "email-tb@example.com",
        "password": "EmailTb1!",
        "full_name": "Email TB",
        "organization_name": "Email Tenant B",
    })

    with patch("app.modules.email_protection.service.test_imap_connection", return_value=True):
        create_resp = await client.post(
            "/api/v1/email/accounts",
            json={
                "email_address": "secret-b@company.com",
                "imap_host": "imap.company.com",
                "imap_port": 993,
                "password": "s3c",
                "use_ssl": True,
            },
            headers=headers(token_b),
        )
    account_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/email/accounts/{account_id}", headers=headers(token_a))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_account_list_scoped_to_tenant(client):
    """Gli account di org_B non appaiono nella lista di org_A."""
    token_a = await register_and_get_token(client, {
        "email": "email-list-ta@example.com",
        "password": "EmailListTa1!",
        "full_name": "Email List TA",
        "organization_name": "Email List Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "email-list-tb@example.com",
        "password": "EmailListTb1!",
        "full_name": "Email List TB",
        "organization_name": "Email List Tenant B",
    })

    with patch("app.modules.email_protection.service.test_imap_connection", return_value=True):
        await client.post(
            "/api/v1/email/accounts",
            json={
                "email_address": "only-b@company.com",
                "imap_host": "imap.company.com",
                "imap_port": 993,
                "password": "s3c",
                "use_ssl": True,
            },
            headers=headers(token_b),
        )

    resp_a = await client.get("/api/v1/email/accounts", headers=headers(token_a))
    assert resp_a.status_code == 200
    emails_a = [a["email_address"] for a in resp_a.json()]
    assert "only-b@company.com" not in emails_a
