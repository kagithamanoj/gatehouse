"""Cost math: priced models bill correctly, unknown models bill zero."""

from app import cost as cost_mod
from app.config import DEFAULT_PRICE_TABLE

from .conftest import ADMIN_HEADERS, auth_headers


def test_known_model_cost():
    # gpt-4o: $2.50 / 1M input, $10.00 / 1M output.
    assert cost_mod.estimate_cost_usd("gpt-4o", 1_000_000, 1_000_000,
                                     DEFAULT_PRICE_TABLE) == 12.50


def test_mini_model_cost():
    assert cost_mod.estimate_cost_usd("gpt-4o-mini", 1_000_000, 0,
                                     DEFAULT_PRICE_TABLE) == 0.15


def test_unknown_model_costs_zero():
    assert cost_mod.estimate_cost_usd("some-future-model", 5000, 5000,
                                     DEFAULT_PRICE_TABLE) == 0.0


def test_cost_rounding():
    import pytest
    got = cost_mod.estimate_cost_usd("gpt-4o", 3, 7, DEFAULT_PRICE_TABLE)
    expected = 3 * 2.50 / 1_000_000 + 7 * 10.00 / 1_000_000
    assert got == pytest.approx(expected, abs=1e-6)


def test_stats_accumulate_cost(app_client, user_key):
    client, _ = app_client
    for _ in range(3):
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini",
                  "messages": [{"role": "user", "content": "hello world"}]},
            headers=auth_headers(user_key),
        )
        assert resp.status_code == 200
        assert resp.json()["gatehouse"]["cost_usd"] > 0

    stats = client.get("/admin/stats", headers=ADMIN_HEADERS).json()["usage_by_key"]
    assert len(stats) == 1
    row = stats[0]
    assert row["key_id"] == user_key["key_id"]
    assert row["requests"] == 3
    assert row["cost_usd"] > 0
    assert row["prompt_tokens"] > 0
