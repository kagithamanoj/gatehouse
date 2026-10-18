"""Rate limiting: token bucket caps bursts and refills over time."""

import time

from fastapi.testclient import TestClient

from app import auth as auth_mod
from app.config import Settings
from app.main import create_app
from .conftest import ADMIN_HEADERS


def _limited_client(tmp_path, rpm, burst):
    settings = Settings(
        upstream_mode="mock",
        admin_api_key="test-admin-key",
        db_path=str(tmp_path / "rl.db"),
        rate_limit_rpm=rpm,
        rate_limit_burst=burst,
    )
    app = create_app(settings)
    created = auth_mod.create_key(app.state.db, "rl-key", rpm=rpm, burst=burst)
    client = TestClient(app)
    client.app_state = app.state  # expose for tests that need the app
    return client, created


def _chat(client, key):
    return client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {key['api_key']}"},
    )


def test_burst_then_429(tmp_path):
    client, key = _limited_client(tmp_path, rpm=60, burst=2)
    with client:
        assert _chat(client, key).status_code == 200
        assert _chat(client, key).status_code == 200
        resp = _chat(client, key)
        assert resp.status_code == 429
        assert "retry_after_seconds" in resp.json()
        assert "Retry-After" in resp.headers


def test_bucket_refills(tmp_path):
    client, key = _limited_client(tmp_path, rpm=60, burst=1)
    with client:
        assert _chat(client, key).status_code == 200
        assert _chat(client, key).status_code == 429
        time.sleep(1.2)  # 60 rpm refills 1 token per second
        assert _chat(client, key).status_code == 200


def test_limits_are_per_key(tmp_path):
    client, key = _limited_client(tmp_path, rpm=60, burst=1)
    with client:
        other = auth_mod.create_key(client.app_state.db, "other", rpm=60, burst=1)
        assert _chat(client, key).status_code == 200
        assert _chat(client, key).status_code == 429
        # A different key still has its own bucket.
        assert _chat(client, other).status_code == 200
