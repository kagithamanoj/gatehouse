"""Auth: valid keys pass, bad/missing/revoked keys are rejected."""

from app import auth as auth_mod
from .conftest import ADMIN_HEADERS, auth_headers


def _chat(client, headers):
    return client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": [{"role": "user", "content": "hello"}]},
        headers=headers,
    )


def test_valid_key_allowed(app_client, user_key):
    client, _ = app_client
    resp = _chat(client, auth_headers(user_key))
    assert resp.status_code == 200


def test_missing_key_rejected(app_client):
    client, _ = app_client
    assert _chat(client, {}).status_code == 401


def test_wrong_key_rejected(app_client):
    client, _ = app_client
    resp = _chat(client, {"Authorization": "Bearer gatehouse_wrongkey"})
    assert resp.status_code == 401


def test_revoked_key_rejected(app_client, user_key):
    client, app = app_client
    assert auth_mod.revoke_key(app.state.db, user_key["key_id"]) is True
    assert _chat(client, auth_headers(user_key)).status_code == 401


def test_admin_endpoints_need_admin_key(app_client):
    client, _ = app_client
    assert client.get("/admin/stats").status_code == 401
    assert client.get("/admin/stats", headers={"X-Admin-Key": "nope"}).status_code == 401
    assert client.get("/admin/stats", headers=ADMIN_HEADERS).status_code == 200


def test_admin_create_and_revoke_key(app_client):
    client, _ = app_client
    created = client.post("/admin/keys", json={"name": "svc-a"}, headers=ADMIN_HEADERS)
    assert created.status_code == 200
    body = created.json()
    assert body["api_key"].startswith("gatehouse_")

    # Plaintext key is never stored; listing must not leak it.
    listed = client.get("/admin/keys", headers=ADMIN_HEADERS).json()["keys"]
    assert all("api_key" not in k for k in listed)

    revoked = client.post(f"/admin/keys/{body['key_id']}/revoke", headers=ADMIN_HEADERS)
    assert revoked.status_code == 200
    assert _chat(client, {"Authorization": f"Bearer {body['api_key']}"}).status_code == 401
