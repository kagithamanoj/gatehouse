"""Gatehouse AI Gateway: FastAPI app wiring auth, rate limits, PII redaction,
prompt-injection screening, audit logging, and cost tracking around an LLM upstream."""

from __future__ import annotations

import hashlib
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from . import audit as audit_mod
from . import auth as auth_mod
from . import cost as cost_mod
from . import injection as injection_mod
from . import pii as pii_mod
from . import upstream as upstream_mod
from .config import Settings, load_settings
from .db import Database
from .ratelimit import TokenBucketLimiter


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _set_text(content, new_text: str):
    if isinstance(content, str):
        return new_text
    if isinstance(content, list):
        out = []
        first = True
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text" and first:
                out.append({**p, "text": new_text})
                first = False
            else:
                out.append(p)
        return out
    return content


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    db = Database(settings.db_path)
    limiter = TokenBucketLimiter()

    app = FastAPI(title="Gatehouse AI Gateway", version="1.0.0")
    app.state.settings = settings
    app.state.db = db
    app.state.limiter = limiter

    def require_key(authorization: str | None = Header(default=None)) -> dict:
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        record = auth_mod.verify_key(db, token or "")
        if record is None:
            raise HTTPException(status_code=401, detail="invalid or revoked API key")
        return record

    def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
        if not x_admin_key or x_admin_key != settings.admin_api_key:
            raise HTTPException(status_code=401, detail="invalid admin key")

    @app.get("/health")
    def health():
        return {"status": "ok", "upstream_mode": settings.upstream_mode}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request, key: dict = Depends(require_key)):
        started = time.monotonic()
        body = await request.json()
        model = body.get("model") or settings.default_model
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="messages must be a non-empty list")

        # Rate limit.
        rpm = key["rpm"] or settings.rate_limit_rpm
        burst = key["burst"] or settings.rate_limit_burst
        allowed, retry_after = limiter.allow(key["key_id"], float(rpm), float(burst))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "rate limit exceeded", "retry_after_seconds": round(retry_after, 2)},
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        # Injection scan over the full prompt text.
        prompt_text = "\n".join(_text_of(m.get("content", "")) for m in messages)
        prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        scan = injection_mod.scan(
            prompt_text,
            flag_score=settings.injection_flag_score,
            block_score=settings.injection_block_score,
            policy=settings.injection_policy,
        )

        gatehouse_meta = {
            "injection_verdict": scan["verdict"],
            "injection_score": scan["score"],
            "injection_signals": scan["matched"],
        }

        if scan["verdict"] == "block":
            latency_ms = (time.monotonic() - started) * 1000
            audit_mod.log_request(
                db, key_id=key["key_id"], model=model,
                prompt_tokens=cost_mod.estimate_tokens(prompt_text),
                completion_tokens=0, latency_ms=latency_ms,
                injection_verdict="block", injection_score=scan["score"],
                redactions={}, cost_usd=0.0, prompt_sha256=prompt_sha,
                had_pii=False, upstream_mode=settings.upstream_mode,
                error="blocked: prompt injection",
            )
            return JSONResponse(
                status_code=403,
                content={"error": "request blocked by injection policy", "gatehouse": gatehouse_meta},
            )

        # PII redact the prompt before it reaches the upstream.
        redacted_messages = []
        prompt_redactions: dict = {}
        for m in messages:
            new_content, counts = pii_mod.redact(_text_of(m.get("content", "")))
            prompt_redactions = pii_mod.merge_counts(prompt_redactions, counts)
            redacted_messages.append({**m, "content": _set_text(m.get("content"), new_content)})
        had_pii = bool(prompt_redactions)

        # Upstream call.
        upstream_payload = dict(body)
        upstream_payload["model"] = model
        upstream_payload["messages"] = redacted_messages
        try:
            upstream_resp = upstream_mod.call_upstream(
                settings.upstream_mode, settings.upstream_base_url,
                settings.upstream_api_key, upstream_payload, settings.upstream_timeout_s,
            )
            upstream_error = None
        except upstream_mod.UpstreamError as exc:
            upstream_error = str(exc)
            upstream_resp = None

        completion_redactions: dict = {}
        prompt_tokens = cost_mod.estimate_tokens(prompt_text)
        completion_tokens = 0

        if upstream_resp is not None:
            if settings.redact_completions:
                for choice in upstream_resp.get("choices", []):
                    msg = choice.get("message", {})
                    new_content, counts = pii_mod.redact(_text_of(msg.get("content", "")))
                    completion_redactions = pii_mod.merge_counts(completion_redactions, counts)
                    msg["content"] = _set_text(msg.get("content"), new_content)
            usage = upstream_resp.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens") or prompt_tokens)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            if not usage.get("completion_tokens"):
                completion_text = " ".join(
                    _text_of(c.get("message", {}).get("content", ""))
                    for c in upstream_resp.get("choices", [])
                )
                completion_tokens = cost_mod.estimate_tokens(completion_text)

        total_redactions = pii_mod.merge_counts(prompt_redactions, completion_redactions)
        cost_usd = cost_mod.estimate_cost_usd(model, prompt_tokens, completion_tokens, settings.price_table)
        latency_ms = (time.monotonic() - started) * 1000

        audit_mod.log_request(
            db, key_id=key["key_id"], model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            latency_ms=latency_ms, injection_verdict=scan["verdict"],
            injection_score=scan["score"], redactions=total_redactions,
            cost_usd=cost_usd, prompt_sha256=prompt_sha, had_pii=had_pii,
            upstream_mode=settings.upstream_mode, error=upstream_error,
        )

        gatehouse_meta.update({
            "prompt_redactions": prompt_redactions,
            "completion_redactions": completion_redactions,
            "cost_usd": cost_usd,
            "latency_ms": round(latency_ms, 1),
        })

        if upstream_error:
            return JSONResponse(
                status_code=502,
                content={"error": "upstream failure", "detail": upstream_error, "gatehouse": gatehouse_meta},
            )

        upstream_resp["gatehouse"] = gatehouse_meta
        return JSONResponse(status_code=200, content=upstream_resp)

    @app.post("/admin/keys")
    def admin_create_key(payload: dict, _admin: None = Depends(require_admin)):
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        return auth_mod.create_key(db, name, payload.get("rpm"), payload.get("burst"))

    @app.get("/admin/keys")
    def admin_list_keys(_admin: None = Depends(require_admin)):
        return {"keys": auth_mod.list_keys(db)}

    @app.post("/admin/keys/{key_id}/revoke")
    def admin_revoke_key(key_id: str, _admin: None = Depends(require_admin)):
        if not auth_mod.revoke_key(db, key_id):
            raise HTTPException(status_code=404, detail="key not found")
        return {"key_id": key_id, "revoked": True}

    @app.get("/admin/stats")
    def admin_stats(_admin: None = Depends(require_admin)):
        return {"usage_by_key": audit_mod.stats(db)}

    @app.get("/admin/audit")
    def admin_audit(limit: int = 50, _admin: None = Depends(require_admin)):
        return {"audit": audit_mod.recent(db, limit)}

    return app


app = create_app()
