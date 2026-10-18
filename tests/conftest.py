"""Shared fixtures: a fresh app with an isolated SQLite DB per test."""

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app.config import Settings
from app.main import create_app


@pytest.fixture()
def app_client(tmp_path):
    settings = Settings(
        upstream_mode="mock",
        admin_api_key="test-admin-key",
        db_path=str(tmp_path / "test.db"),
        rate_limit_rpm=6000,
        rate_limit_burst=100,
        injection_policy="block",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app


@pytest.fixture()
def user_key(app_client):
    client, app = app_client
    created = auth_mod.create_key(app.state.db, "test-key")
    return created  # {"key_id", "api_key", "name", ...}


def auth_headers(key: dict) -> dict:
    return {"Authorization": f"Bearer {key['api_key']}"}


ADMIN_HEADERS = {"X-Admin-Key": "test-admin-key"}
