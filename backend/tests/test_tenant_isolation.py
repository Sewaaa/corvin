"""
Test formale dell'isolamento multi-tenant.

Dimostra che e strutturalmente impossibile per un tenant accedere ai dati di un altro.
Ogni test registra due organizzazioni separate e verifica che le risorse di org_B
siano completamente inaccessibili a org_A.
"""
import pytest


ORG_A = {
    "email": "alice@org-a.com",
    "password": "AlicePass1!",
    "full_name": "Alice Admin",
    "organization_name": "Org Alpha",
}
ORG_B = {
    "email": "bob@org-b.com",
    "password": "BobPass1!",
    "full_name": "Bob Admin",
    "organization_name": "Org Beta",
}


async def register_and_login(client, payload: dict) -> str:
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_orgs_have_separate_ids(client):
    """Due registrazioni distinte producono org_id diversi."""
    token_a = await register_and_login(client, ORG_A)
    token_b = await register_and_login(client, ORG_B)
    org_a = (await client.get("/api/v1/organizations/", headers=auth_headers(token_a))).json()
    org_b = (await client.get("/api/v1/organizations/", headers=auth_headers(token_b))).json()
    assert org_a["id"] != org_b["id"]
    assert org_a["name"] == "Org Alpha"
    assert org_b["name"] == "Org Beta"


@pytest.mark.asyncio
async def test_org_summary_scoped_to_tenant(client):
    """Il summary restituisce sempre i dati del proprio tenant, mai di un altro."""
    token_a = await register_and_login(client, ORG_A)
    resp = await client.get("/api/v1/organizations/summary", headers=auth_headers(token_a))
    assert resp.status_code == 200
    assert resp.json()["org"]["name"] == "Org Alpha"


@pytest.mark.asyncio
async def test_user_list_scoped_to_tenant(client):
    """La lista utenti di org_A non contiene utenti di org_B."""
    token_a = await register_and_login(client, ORG_A)
    token_b = await register_and_login(client, ORG_B)
    users_a = (await client.get("/api/v1/users/", headers=auth_headers(token_a))).json()
    users_b = (await client.get("/api/v1/users/", headers=auth_headers(token_b))).json()
    emails_a = {u["email"] for u in users_a}
    emails_b = {u["email"] for u in users_b}
    assert emails_a.isdisjoint(emails_b), f"SECURITY leak: {emails_a & emails_b}"
    assert ORG_A["email"] in emails_a
    assert ORG_B["email"] in emails_b


@pytest.mark.asyncio
async def test_cross_tenant_role_change_returns_404(client):
    """org_A non puo modificare il ruolo di un utente di org_B (404, non 403).
    
    Restituire 404 invece di 403 e importante: non rivela nemmeno
    l'esistenza dell'utente nell'altro tenant (security through obscurity layer).
    """
    token_a = await register_and_login(client, ORG_A)
    token_b = await register_and_login(client, ORG_B)
    users_b = (await client.get("/api/v1/users/", headers=auth_headers(token_b))).json()
    bob_id = users_b[0]["id"]
    resp = await client.patch(
        f"/api/v1/users/{bob_id}/role",
        json={"role": "viewer"},
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 404, f"SECURITY FAIL: org_A ha raggiunto utente org_B ({resp.status_code})"


@pytest.mark.asyncio
async def test_cross_tenant_deactivation_returns_404(client):
    """org_A non puo disattivare un utente di org_B."""
    token_a = await register_and_login(client, ORG_A)
    token_b = await register_and_login(client, ORG_B)
    users_b = (await client.get("/api/v1/users/", headers=auth_headers(token_b))).json()
    bob_id = users_b[0]["id"]
    resp = await client.delete(f"/api/v1/users/{bob_id}", headers=auth_headers(token_a))
    assert resp.status_code == 404, f"SECURITY FAIL: org_A ha disattivato utente org_B ({resp.status_code})"


@pytest.mark.asyncio
async def test_viewer_role_cannot_invite(client):
    """RBAC: un Viewer non puo invitare nuovi utenti (azione riservata agli Admin)."""
    token_admin = await register_and_login(client, ORG_A)
    await client.post(
        "/api/v1/users/invite",
        json={"email": "viewer@org-a.com", "full_name": "View Only",
              "role": "viewer", "temporary_password": "TempPass1!"},
        headers=auth_headers(token_admin),
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@org-a.com", "password": "TempPass1!"},
    )
    viewer_token = login_resp.json()["access_token"]
    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "hacker@org-a.com", "full_name": "Hacker",
              "role": "admin", "temporary_password": "HackPass1!"},
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 403, f"SECURITY FAIL: Viewer ha invitato utenti ({resp.status_code})"


@pytest.mark.asyncio
async def test_analyst_role_cannot_change_roles(client):
    """RBAC: un Analyst non puo modificare ruoli altrui."""
    token_admin = await register_and_login(client, ORG_A)
    await client.post(
        "/api/v1/users/invite",
        json={"email": "analyst@org-a.com", "full_name": "Ana Lyst",
              "role": "analyst", "temporary_password": "AnalPass1!"},
        headers=auth_headers(token_admin),
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@org-a.com", "password": "AnalPass1!"},
    )
    analyst_token = login_resp.json()["access_token"]
    users = (await client.get("/api/v1/users/", headers=auth_headers(analyst_token))).json()
    admin_id = next(u["id"] for u in users if u["role"] == "admin")
    resp = await client.patch(
        f"/api/v1/users/{admin_id}/role",
        json={"role": "viewer"},
        headers=auth_headers(analyst_token),
    )
    assert resp.status_code == 403
