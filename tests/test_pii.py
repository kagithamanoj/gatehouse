"""PII redaction: emails, phones, SSNs, and Luhn-valid cards are redacted."""

from app import pii as pii_mod


def test_email_redacted():
    text, counts = pii_mod.redact("contact john.doe@example.com for help")
    assert "[REDACTED:EMAIL]" in text
    assert "john.doe@example.com" not in text
    assert counts == {"EMAIL": 1}


def test_phone_redacted():
    for phone in ["(555) 123-4567", "555-123-4567", "555.123.4567", "+1 555 123 4567"]:
        text, counts = pii_mod.redact(f"call me at {phone}")
        assert "[REDACTED:PHONE]" in text, phone
        assert counts.get("PHONE") == 1


def test_ssn_redacted():
    text, counts = pii_mod.redact("ssn 123-45-6789 on file")
    assert "[REDACTED:SSN]" in text
    assert counts == {"SSN": 1}


def test_valid_card_redacted():
    text, counts = pii_mod.redact("card 4111111111111111 charged")
    assert "[REDACTED:CARD]" in text
    assert counts == {"CARD": 1}


def test_invalid_card_not_redacted():
    # Fails the Luhn check: must not be treated as a card number.
    text, counts = pii_mod.redact("ref 4111111111111112 pending")
    assert "[REDACTED:CARD]" not in text
    assert counts == {}


def test_short_numbers_not_redacted():
    text, counts = pii_mod.redact("order 42 shipped, zip 75234")
    assert counts == {}
    assert text == "order 42 shipped, zip 75234"


def test_multiple_types_counted():
    text, counts = pii_mod.redact(
        "email a@b.com and ssn 123-45-6789, card 4111111111111111"
    )
    assert counts == {"EMAIL": 1, "SSN": 1, "CARD": 1}
    assert "[REDACTED:EMAIL]" in text
    assert "[REDACTED:SSN]" in text
    assert "[REDACTED:CARD]" in text


def test_card_inside_longer_digit_string_not_split():
    # Card redaction runs before phone matching so a card number cannot be
    # partially eaten by the phone pattern.
    text, _ = pii_mod.redact("pay 4111111111111111 now")
    assert "4111111111" not in text


def test_completion_redaction_end_to_end(app_client, user_key, monkeypatch):
    """A PII leak in the upstream completion is scrubbed before the client sees it."""
    from .conftest import auth_headers
    from app import upstream as upstream_mod

    client, _ = app_client

    def fake_upstream(mode, base_url, api_key, payload, timeout_s):
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1,
            "model": payload.get("model"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant",
                            "content": "Sure, I emailed jane.smith@example.com about it."},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
        }

    monkeypatch.setattr(upstream_mod, "call_upstream", fake_upstream)
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "mock-llm",
              "messages": [{"role": "user", "content": "summarize this"}]},
        headers=auth_headers(user_key),
    )
    assert resp.status_code == 200
    content = resp.json()["choices"][0]["message"]["content"]
    assert "jane.smith@example.com" not in content
    assert "[REDACTED:EMAIL]" in content
    assert resp.json()["gatehouse"]["completion_redactions"] == {"EMAIL": 1}
