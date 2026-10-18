"""Audit log: every request is recorded, raw PII never lands in the DB."""

import json

from .conftest import ADMIN_HEADERS, auth_headers


def test_request_is_audited(app_client, user_key):
    client, app = app_client
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm",
              "messages": [{"role": "user", "content": "hello there"}]},
        headers=auth_headers(user_key),
    )
    assert resp.status_code == 200

    rows = app.state.db.query("SELECT * FROM audit_log")
    assert len(rows) == 1
    row = dict(rows[0])
    assert row["key_id"] == user_key["key_id"]
    assert row["model"] == "mock-llm"
    assert row["prompt_tokens"] > 0
    assert row["completion_tokens"] > 0
    assert row["latency_ms"] > 0
    assert row["injection_verdict"] == "allow"
    assert len(row["prompt_sha256"]) == 64  # sha256 hex, never raw text


def test_raw_pii_never_stored(app_client, user_key):
    client, app = app_client
    secret_email = "victim.secret@example.com"
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": [
            {"role": "user", "content": f"my email is {secret_email}"}]},
        headers=auth_headers(user_key),
    )
    assert resp.status_code == 200
    assert resp.json()["gatehouse"]["prompt_redactions"] == {"EMAIL": 1}

    # The raw address must appear nowhere in the database.
    dump = " ".join(str(v) for row in app.state.db.query("SELECT * FROM audit_log")
                    for v in dict(row).values())
    assert secret_email not in dump

    row = dict(app.state.db.query("SELECT * FROM audit_log")[0])
    assert row["had_pii"] == 1
    assert json.loads(row["redactions"]) == {"EMAIL": 1}


def test_admin_audit_endpoint(app_client, user_key):
    client, _ = app_client
    client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers(user_key),
    )
    resp = client.get("/admin/audit?limit=10", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    entries = resp.json()["audit"]
    assert len(entries) == 1
    assert entries[0]["key_id"] == user_key["key_id"]
