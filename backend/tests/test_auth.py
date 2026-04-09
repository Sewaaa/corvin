"""
Test suite per il modulo auth.
Copre: register, login, refresh token, MFA setup/verify, /me.
"""
import pytest


REGISTER_PAYLOAD = {
    "email": "test@example.com",
    "password": "Test1234!",
    "full_name": "Test User",
    "organization_name": "Test Org",
}


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    # Generic conflict error — must not reveal whether email exists
    assert response.status_code == 409
    assert "Registrazione fallita" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client):
    payload = {**REGISTER_PAYLOAD, "email": "weak@example.com", "password": "short"}
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    payload = {**REGISTER_PAYLOAD, "email": "not-an-email"}
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": "WrongPass1!"},
    )
    assert response.status_code == 401
    # Error message must NOT distinguish wrong password from unknown email
    assert "Email o password non validi" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "Test1234!"},
    )
    assert response.status_code == 401
    # Same generic message — prevents user enumeration
    assert "Email o password non validi" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_token_success(client):
    reg = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    refresh_token = reg.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    # Rotated refresh token should differ from the original
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(client):
    reg = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    access_token = reg.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},  # wrong token type
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /me endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me(client):
    reg = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    access_token = reg.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == REGISTER_PAYLOAD["email"]
    assert data["role"] == "admin"
    assert data["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# MFA setup + verify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mfa_setup_and_verify(client):
    import pyotp

    reg = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup: generate TOTP secret
    setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["secret"]
    assert len(secret) > 0

    # Verify: submit correct TOTP code
    code = pyotp.TOTP(secret).now()
    verify_resp = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": code},
        headers=headers,
    )
    assert verify_resp.status_code == 200
    assert "MFA enabled" in verify_resp.json()["message"]


@pytest.mark.asyncio
async def test_mfa_verify_wrong_code(client):
    reg = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post("/api/v1/auth/mfa/setup", headers=headers)

    verify_resp = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": "000000"},
        headers=headers,
    )
    assert verify_resp.status_code == 400


# ---------------------------------------------------------------------------
# Tenant isolation sanity check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_orgs_get_separate_tokens(client):
    """Registra due utenti in org diverse — i token devono avere org_id diversi."""
    import base64, json

    reg1 = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    reg2 = await client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "other@example.com", "organization_name": "Other Org"},
    )

    def decode_jwt_payload(token: str) -> dict:
        part = token.split(".")[1]
        # Add padding
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))

    payload1 = decode_jwt_payload(reg1.json()["access_token"])
    payload2 = decode_jwt_payload(reg2.json()["access_token"])

    assert payload1["org_id"] != payload2["org_id"], (
        "SECURITY: two different orgs must never share an org_id in their tokens"
    )
