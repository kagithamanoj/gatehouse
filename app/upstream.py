"""Upstream LLM calls: mock mode for demos/tests, real OpenAI-compatible mode."""

from __future__ import annotations

import time
import uuid

import httpx

from .cost import estimate_tokens


def _mock_response(model: str, messages: list[dict]) -> dict:
    user_texts = [m.get("content", "") for m in messages if m.get("role") == "user"]
    last_user = user_texts[-1] if user_texts else ""
    if isinstance(last_user, list):  # content parts
        last_user = " ".join(p.get("text", "") for p in last_user if isinstance(p, dict))
    content = (
        "[mock upstream] Processed {} message(s). "
        "Last user message was {} chars. "
        "This is a deterministic demo response; point Gatehouse at a real "
        "OpenAI-compatible endpoint for live completions."
    ).format(len(messages), len(last_user or ""))
    prompt_tokens = sum(estimate_tokens(_text_of(m.get("content", ""))) for m in messages)
    completion_tokens = estimate_tokens(content)
    return {
        "id": "chatcmpl-mock-" + uuid.uuid4().hex[:12],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def call_upstream(mode: str, base_url: str, api_key: str, payload: dict,
                  timeout_s: float) -> dict:
    """Call the upstream and return an OpenAI-style chat completion dict."""
    model = payload.get("model", "mock-llm")
    messages = payload.get("messages", [])
    if mode == "mock":
        return _mock_response(model, messages)
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=timeout_s)
    except httpx.RequestError as exc:
        raise UpstreamError(f"upstream unreachable: {exc}") from exc
    if resp.status_code >= 400:
        raise UpstreamError(f"upstream returned HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


class UpstreamError(Exception):
    pass
