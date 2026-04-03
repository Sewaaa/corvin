"""
Test suite per il modulo Notifications.

Strategia:
- Unit test: HMAC signature, deduplication logic, encrypt/decrypt secret
- Integration test: CRUD notifiche, mark-read, webhook CRUD, tenant isolation
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.notifications.service import (
    _compute_hmac,
    decrypt_secret,
    encrypt_secret,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REGISTER = {
    "email": "notif-test@example.com",
    "password": "NotifTest1!",
    "full_name": "Notif Tester",
    "organization_name": "Notif Test Org",
}


async def register_and_get_token(client, payload=None) -> str:
    p = payload or REGISTER
    resp = await client.post("/api/v1/auth/register", json=p)
    assert resp.status_code == 201
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _seed_notification(client, token: str, db_session) -> str:
    """Persiste direttamente una notifica nel DB e restituisce il suo ID."""
    from app.models.notification import Notification, NotificationSeverity
    from app.core.dependencies import get_current_org
    from sqlalchemy import select
    from app.models.organization import Organization
    from app.models.user import User

    # Ricava org_id dall'utente
    import uuid as _uuid
    user_resp = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    org_id = _uuid.UUID(user_resp.json()["organization_id"])

    notif = Notification(
        organization_id=org_id,
        title="Test Notification",
        message="This is a test.",
        severity=NotificationSeverity.HIGH,
        source_module="test",
        source_id="abc123",
    )
    db_session.add(notif)
    await db_session.commit()
    await db_session.refresh(notif)
    return str(notif.id)


# ---------------------------------------------------------------------------
# Unit test: encryption
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_secret_roundtrip():
    secret = "my_webhook_signing_secret!"
    enc = encrypt_secret(secret)
    assert enc != secret
    assert decrypt_secret(enc) == secret


# ---------------------------------------------------------------------------
# Unit test: HMAC
# ---------------------------------------------------------------------------

def test_compute_hmac_correctness():
    payload = b'{"event": "breach.found"}'
    secret = "test_secret"
    sig = _compute_hmac(payload, secret)
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert sig == expected


def test_compute_hmac_different_secrets_differ():
    payload = b"same payload"
    sig1 = _compute_hmac(payload, "secret1")
    sig2 = _compute_hmac(payload, "secret2")
    assert sig1 != sig2


def test_compute_hmac_different_payloads_differ():
    secret = "same_secret"
    sig1 = _compute_hmac(b"payload1", secret)
    sig2 = _compute_hmac(b"payload2", secret)
    assert sig1 != sig2


# ---------------------------------------------------------------------------
# Integration test: create_notification deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deduplication_prevents_duplicate(client, db_session):
    """Stessa dedup_key nelle ultime 24h → seconda chiamata ritorna None."""
    from app.models.notification import NotificationSeverity
    from app.modules.notifications.service import create_notification
    from app.models.organization import Organization
    from sqlalchemy import select

    token = await register_and_get_token(client, {
        "email": "notif-dedup@example.com",
        "password": "NotifDedup1!",
        "full_name": "Notif Dedup",
        "organization_name": "Notif Dedup Org",
    })
    import uuid as _uuid
    user_resp = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    org_id = _uuid.UUID(user_resp.json()["organization_id"])

    n1 = await create_notification(
        db_session,
        organization_id=org_id,
        title="Breach Found",
        message="email@test.com found in breach",
        severity=NotificationSeverity.HIGH,
        source_module="breach_monitor",
        dedup_key=f"breach:{org_id}:email@test.com",
    )
    await db_session.commit()
    assert n1 is not None

    # Seconda chiamata con stessa dedup_key → None
    n2 = await create_notification(
        db_session,
        organization_id=org_id,
        title="Breach Found",
        message="email@test.com found in breach",
        severity=NotificationSeverity.HIGH,
        source_module="breach_monitor",
        dedup_key=f"breach:{org_id}:email@test.com",
    )
    assert n2 is None


@pytest.mark.asyncio
async def test_different_dedup_keys_both_created(client, db_session):
    """Dedup key diverse → entrambe le notifiche vengono create."""
    from app.models.notification import NotificationSeverity
    from app.modules.notifications.service import create_notification

    token = await register_and_get_token(client, {
        "email": "notif-dedup2@example.com",
        "password": "NotifDedup2!",
        "full_name": "Notif Dedup2",
        "organization_name": "Notif Dedup2 Org",
    })
    import uuid as _uuid
    user_resp = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    org_id = _uuid.UUID(user_resp.json()["organization_id"])

    n1 = await create_notification(
        db_session,
        organization_id=org_id,
        title="Alert 1",
        message="msg1",
        severity=NotificationSeverity.MEDIUM,
        source_module="domain",
        dedup_key=f"domain:{org_id}:example.com:spf",
    )
    n2 = await create_notification(
        db_session,
        organization_id=org_id,
        title="Alert 2",
        message="msg2",
        severity=NotificationSeverity.MEDIUM,
        source_module="domain",
        dedup_key=f"domain:{org_id}:example.com:dmarc",
    )
    await db_session.commit()
    assert n1 is not None
    assert n2 is not None
    assert n1.id != n2.id


# ---------------------------------------------------------------------------
# Integration test: GET /notifications/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_notifications_empty(client):
    token = await register_and_get_token(client, {
        "email": "notif-list@example.com",
        "password": "NotifList1!",
        "full_name": "Notif List",
        "organization_name": "Notif List Org",
    })
    resp = await client.get("/api/v1/notifications/", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["unread"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_notifications_shows_seeded(client, db_session):
    token = await register_and_get_token(client, {
        "email": "notif-seed@example.com",
        "password": "NotifSeed1!",
        "full_name": "Notif Seed",
        "organization_name": "Notif Seed Org",
    })
    await _seed_notification(client, token, db_session)

    resp = await client.get("/api/v1/notifications/", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["unread"] >= 1


# ---------------------------------------------------------------------------
# Integration test: PATCH /{id}/read + POST /read-all
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_single_read(client, db_session):
    token = await register_and_get_token(client, {
        "email": "notif-read@example.com",
        "password": "NotifRead1!",
        "full_name": "Notif Read",
        "organization_name": "Notif Read Org",
    })
    notif_id = await _seed_notification(client, token, db_session)

    resp = await client.patch(
        f"/api/v1/notifications/{notif_id}/read",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(client, db_session):
    token = await register_and_get_token(client, {
        "email": "notif-readall@example.com",
        "password": "NotifReadAll1!",
        "full_name": "Notif ReadAll",
        "organization_name": "Notif ReadAll Org",
    })
    await _seed_notification(client, token, db_session)
    await _seed_notification(client, token, db_session)

    resp = await client.post("/api/v1/notifications/read-all", headers=auth_headers(token))
    assert resp.status_code == 200

    list_resp = await client.get("/api/v1/notifications/", headers=auth_headers(token))
    assert list_resp.json()["unread"] == 0


# ---------------------------------------------------------------------------
# Integration test: Webhook CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_webhook(client):
    token = await register_and_get_token(client, {
        "email": "notif-wh@example.com",
        "password": "NotifWh1!",
        "full_name": "Notif WH",
        "organization_name": "Notif WH Org",
    })
    resp = await client.post(
        "/api/v1/notifications/webhooks",
        json={
            "url": "https://hooks.example.com/corvin",
            "secret": "mysecret12345678",
            "events": ["breach.found", "sandbox.malicious"],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["url"] == "https://hooks.example.com/corvin"
    assert "breach.found" in data["events"]
    assert "encrypted_secret" not in data  # secret non esposto


@pytest.mark.asyncio
async def test_list_webhooks(client):
    token = await register_and_get_token(client, {
        "email": "notif-whl@example.com",
        "password": "NotifWhl1!",
        "full_name": "Notif WHL",
        "organization_name": "Notif WHL Org",
    })
    await client.post(
        "/api/v1/notifications/webhooks",
        json={"url": "https://hooks.example.com/1", "events": ["breach.found"]},
        headers=auth_headers(token),
    )
    resp = await client.get("/api/v1/notifications/webhooks", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_delete_webhook(client):
    token = await register_and_get_token(client, {
        "email": "notif-whd@example.com",
        "password": "NotifWhd1!",
        "full_name": "Notif WHD",
        "organization_name": "Notif WHD Org",
    })
    add = await client.post(
        "/api/v1/notifications/webhooks",
        json={"url": "https://hooks.example.com/del", "events": ["*"]},
        headers=auth_headers(token),
    )
    wh_id = add.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/notifications/webhooks/{wh_id}", headers=auth_headers(token)
    )
    assert del_resp.status_code == 204

    list_resp = await client.get("/api/v1/notifications/webhooks", headers=auth_headers(token))
    ids = [w["id"] for w in list_resp.json()]
    assert wh_id not in ids


@pytest.mark.asyncio
async def test_test_webhook_delivers(client):
    """POST /webhooks/{id}/test deve chiamare il webhook e restituire delivered status."""
    token = await register_and_get_token(client, {
        "email": "notif-wht@example.com",
        "password": "NotifWht1!",
        "full_name": "Notif WHT",
        "organization_name": "Notif WHT Org",
    })
    add = await client.post(
        "/api/v1/notifications/webhooks",
        json={"url": "https://hooks.example.com/test", "events": ["*"]},
        headers=auth_headers(token),
    )
    wh_id = add.json()["id"]

    with patch(
        "app.modules.notifications.router.send_webhook",
        new_callable=AsyncMock,
        return_value=True,
    ):
        resp = await client.post(
            f"/api/v1/notifications/webhooks/{wh_id}/test",
            headers=auth_headers(token),
        )
    assert resp.status_code == 200
    assert resp.json()["delivered"] is True


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notifications_scoped_to_tenant(client, db_session):
    """Le notifiche di org_B non appaiono nella lista di org_A."""
    token_a = await register_and_get_token(client, {
        "email": "notif-ta@example.com",
        "password": "NotifTa1!",
        "full_name": "Notif TA",
        "organization_name": "Notif Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "notif-tb@example.com",
        "password": "NotifTb1!",
        "full_name": "Notif TB",
        "organization_name": "Notif Tenant B",
    })

    await _seed_notification(client, token_b, db_session)

    resp_a = await client.get("/api/v1/notifications/", headers=auth_headers(token_a))
    resp_b = await client.get("/api/v1/notifications/", headers=auth_headers(token_b))

    assert resp_b.json()["total"] >= 1
    # A non vede le notifiche di B (conteggi disgiunti)
    ids_a = {n["id"] for n in resp_a.json()["items"]}
    ids_b = {n["id"] for n in resp_b.json()["items"]}
    assert ids_a.isdisjoint(ids_b)


@pytest.mark.asyncio
async def test_cross_tenant_notification_detail_404(client, db_session):
    token_a = await register_and_get_token(client, {
        "email": "notif-ta2@example.com",
        "password": "NotifTa2!",
        "full_name": "Notif TA2",
        "organization_name": "Notif Tenant A2",
    })
    token_b = await register_and_get_token(client, {
        "email": "notif-tb2@example.com",
        "password": "NotifTb2!",
        "full_name": "Notif TB2",
        "organization_name": "Notif Tenant B2",
    })
    notif_id = await _seed_notification(client, token_b, db_session)

    resp = await client.get(f"/api/v1/notifications/{notif_id}", headers=auth_headers(token_a))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_list_scoped_to_tenant(client):
    token_a = await register_and_get_token(client, {
        "email": "notif-wh-ta@example.com",
        "password": "NotifWhTa1!",
        "full_name": "Notif WH TA",
        "organization_name": "Notif WH Tenant A",
    })
    token_b = await register_and_get_token(client, {
        "email": "notif-wh-tb@example.com",
        "password": "NotifWhTb1!",
        "full_name": "Notif WH TB",
        "organization_name": "Notif WH Tenant B",
    })

    await client.post(
        "/api/v1/notifications/webhooks",
        json={"url": "https://b-only.example.com/hook", "events": ["*"]},
        headers=auth_headers(token_b),
    )

    list_a = await client.get("/api/v1/notifications/webhooks", headers=auth_headers(token_a))
    list_b = await client.get("/api/v1/notifications/webhooks", headers=auth_headers(token_b))

    urls_a = {w["url"] for w in list_a.json()}
    urls_b = {w["url"] for w in list_b.json()}
    assert "https://b-only.example.com/hook" not in urls_a
    assert "https://b-only.example.com/hook" in urls_b
