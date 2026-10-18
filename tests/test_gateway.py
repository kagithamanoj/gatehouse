"""End-to-end gateway shape: OpenAI-compatible responses plus Gatehouse metadata."""

from .conftest import auth_headers


def test_openai_compatible_shape(app_client, user_key):
    client, _ = app_client
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "say hi"}]},
        headers=auth_headers(user_key),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "mock-llm"
    assert len(body["choices"]) == 1
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["usage"]["total_tokens"] > 0


def test_gatehouse_metadata_present(app_client, user_key):
    client, _ = app_client
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm",
              "messages": [{"role": "user", "content": "hello"}]},
        headers=auth_headers(user_key),
    )
    meta = resp.json()["gatehouse"]
    assert meta["injection_verdict"] == "allow"
    assert meta["prompt_redactions"] == {}
    assert meta["cost_usd"] == 0.0  # mock-llm is unpriced
    assert meta["latency_ms"] >= 0


def test_prompt_pii_redacted_before_upstream(app_client, user_key, monkeypatch):
    """The upstream must only ever see the redacted prompt."""
    from app import upstream as upstream_mod
    from .conftest import auth_headers

    client, _ = app_client
    seen = {}

    def fake_upstream(mode, base_url, api_key, payload, timeout_s):
        seen["messages"] = payload["messages"]
        return {
            "id": "x", "object": "chat.completion", "created": 1,
            "model": payload.get("model"),
            "choices": [{"index": 0,
                         "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }

    monkeypatch.setattr(upstream_mod, "call_upstream", fake_upstream)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": [
            {"role": "user", "content": "my ssn is 123-45-6789"}]},
        headers=auth_headers(user_key),
    )
    assert resp.status_code == 200
    upstream_text = seen["messages"][0]["content"]
    assert "123-45-6789" not in upstream_text
    assert "[REDACTED:SSN]" in upstream_text


def test_empty_messages_rejected(app_client, user_key):
    client, _ = app_client
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm", "messages": []},
        headers=auth_headers(user_key),
    )
    assert resp.status_code == 400


def test_health(app_client):
    client, _ = app_client
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["upstream_mode"] == "mock"
