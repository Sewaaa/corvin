"""
Test suite per il Breach Monitor.

Strategia: mock dell'API HIBP per evitare chiamate reali nei test.
Verifica: k-anonymity (no email in chiaro salvata), logica di deduplicazione,
tenant isolation, e risposta corretta degli endpoint.
"""
import uuid as _uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.breach_monitor.service import _mask_email, _sha256_email


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

FAKE_HIBP_RESPONSE = [
    {
        "Name": "TestBreach2023",
        "BreachDate": "2023-06-15",
        "DataClasses": ["Email addresses", "Passwords"],
        "Description": "A test breach for unit testing purposes.",
    },
    {
        "Name": "AnotherBreach2022",
        "BreachDate": "2022-01-01",
        "DataClasses": ["Email addresses"],
        "Description": None,
    },
]


def _unique_register() -> dict:
    uid = _uuid.uuid4().hex[:8]
    return {
        "email": f"breach-{uid}@example.com",
        "password": "BreachTest1!",
        "full_name": "Breach Tester",
        "organization_name": f"Breach Org {uid}",
    }


async def register_and_get_token(client, payload=None) -> str:
    p = payload or _unique_register()
    resp = await client.post("/api/v1/auth/register", json=p)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test utilità privacy
# ---------------------------------------------------------------------------

def test_mask_email_hides_local_part():
    assert _mask_email("john.doe@example.com") == "j***@example.com"


def test_mask_email_single_char_local():
    assert _mask_email("a@example.com") == "***@example.com"


def test_sha256_is_lowercase_normalized():
    """Lo stesso indirizzo in maiuscolo/minuscolo deve produrre lo stesso hash."""
    assert _sha256_email("User@Example.COM") == _sha256_email("user@example.com")


def test_sha256_different_emails_differ():
    assert _sha256_email("alice@example.com") != _sha256_email("bob@example.com")


# ---------------------------------------------------------------------------
# Test endpoint: aggiunta email
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_email_to_monitoring(client):
    token = await register_and_get_token(client)
    resp = await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["monitor@example.com"]},
        headers=headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 1
    assert data[0]["email_masked"] == "m***@example.com"
    # Verifica che l'email in chiaro NON sia mai presente nella risposta
    assert "monitor@example.com" not in str(data)


@pytest.mark.asyncio
async def test_add_duplicate_email_is_skipped(client):
    token = await register_and_get_token(client)
    await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["dup@example.com"]},
        headers=headers(token),
    )
    # Seconda aggiunta della stessa email: deve restituire lista vuota (skippata)
    resp = await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["dup@example.com"]},
        headers=headers(token),
    )
    assert resp.status_code == 201
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_multiple_emails(client):
    token = await register_and_get_token(client)
    resp = await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["one@example.com", "two@example.com", "three@example.com"]},
        headers=headers(token),
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_add_invalid_email_rejected(client):
    token = await register_and_get_token(client)
    resp = await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["not-an-email"]},
        headers=headers(token),
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Test endpoint: check con mock HIBP
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_returns_breaches_from_hibp(client):
    """Simula una risposta HIBP con 2 breach — verifica che vengano salvate."""
    token = await register_and_get_token(client)

    with patch(
        "app.modules.breach_monitor.service._query_hibp_breaches",
        new=AsyncMock(return_value=FAKE_HIBP_RESPONSE),
    ):
        resp = await client.post(
            "/api/v1/breach/check",
            json={"emails": ["victim@example.com"]},
            headers=headers(token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    result = data[0]
    assert result["is_breached"] is True
    assert result["breach_count"] == 2
    assert result["email_masked"] == "v***@example.com"
    # Email in chiaro MAI nella risposta
    assert "victim@example.com" not in str(data)
    breach_names = [b["breach_name"] for b in result["breaches"]]
    assert "TestBreach2023" in breach_names
    assert "AnotherBreach2022" in breach_names


@pytest.mark.asyncio
async def test_check_no_breaches(client):
    """HIBP risponde con lista vuota — email pulita."""
    token = await register_and_get_token(client)

    with patch(
        "app.modules.breach_monitor.service._query_hibp_breaches",
        new=AsyncMock(return_value=[]),
    ):
        resp = await client.post(
            "/api/v1/breach/check",
            json={"emails": ["clean@example.com"]},
            headers=headers(token),
        )

    data = resp.json()
    assert data[0]["is_breached"] is False
    assert data[0]["breach_count"] == 0


@pytest.mark.asyncio
async def test_check_deduplicates_breaches(client):
    """Chiamare check due volte sulla stessa email non deve duplicare i record."""
    token = await register_and_get_token(client)

    with patch(
        "app.modules.breach_monitor.service._query_hibp_breaches",
        new=AsyncMock(return_value=FAKE_HIBP_RESPONSE),
    ):
        await client.post(
            "/api/v1/breach/check",
            json={"emails": ["dedup@example.com"]},
            headers=headers(token),
        )
        resp2 = await client.post(
            "/api/v1/breach/check",
            json={"emails": ["dedup@example.com"]},
            headers=headers(token),
        )

    # Al secondo check le stesse breach esistono già — breach_count deve essere 2, non 4
    assert resp2.json()[0]["breach_count"] == 2


# ---------------------------------------------------------------------------
# Test: tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_list_scoped_to_tenant(client):
    """Le email monitorate di org_A non devono essere visibili da org_B."""
    token_a = await register_and_get_token(client)
    token_b = await register_and_get_token(client)

    # org_A aggiunge un'email
    await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["secret@org-a.com"]},
        headers=headers(token_a),
    )

    # org_B non deve vederla
    resp_b = await client.get("/api/v1/breach/emails", headers=headers(token_b))
    assert resp_b.status_code == 200
    emails_b = [e["email_masked"] for e in resp_b.json()]
    assert "s***@org-a.com" not in emails_b


@pytest.mark.asyncio
async def test_cannot_delete_email_of_other_org(client):
    """org_A non può rimuovere un'email monitorata da org_B (→ 404)."""
    token_a = await register_and_get_token(client)
    token_b = await register_and_get_token(client)

    # org_B aggiunge un'email e recupera il suo id
    add_resp = await client.post(
        "/api/v1/breach/emails",
        json={"emails": ["secret2@org-b.com"]},
        headers=headers(token_b),
    )
    email_id = add_resp.json()[0]["id"]

    # org_A tenta di eliminare l'email di org_B
    del_resp = await client.delete(
        f"/api/v1/breach/emails/{email_id}",
        headers=headers(token_a),
    )
    assert del_resp.status_code == 404
