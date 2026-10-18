"""Audit logging: one row per gateway request. Raw prompt text is never stored."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_request(db, *, key_id: str, model: str | None, prompt_tokens: int,
                completion_tokens: int, latency_ms: float, injection_verdict: str,
                injection_score: float, redactions: dict, cost_usd: float,
                prompt_sha256: str, had_pii: bool, upstream_mode: str,
                error: str | None = None) -> int:
    cur = db.execute(
        "INSERT INTO audit_log (ts, key_id, model, prompt_tokens, completion_tokens,"
        " latency_ms, injection_verdict, injection_score, redactions, cost_usd,"
        " prompt_sha256, had_pii, upstream_mode, error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (_utcnow(), key_id, model, prompt_tokens, completion_tokens, latency_ms,
         injection_verdict, injection_score, json.dumps(redactions), cost_usd,
         prompt_sha256, 1 if had_pii else 0, upstream_mode, error),
    )
    return cur.lastrowid


def recent(db, limit: int = 50) -> list[dict]:
    rows = db.query(
        "SELECT id, ts, key_id, model, prompt_tokens, completion_tokens, latency_ms,"
        " injection_verdict, injection_score, redactions, cost_usd, prompt_sha256,"
        " had_pii, upstream_mode, error"
        " FROM audit_log ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 500)),),
    )
    return [dict(r) for r in rows]


def stats(db) -> list[dict]:
    rows = db.query(
        "SELECT key_id,"
        " COUNT(*) AS requests,"
        " COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,"
        " COALESCE(SUM(completion_tokens), 0) AS completion_tokens,"
        " COALESCE(SUM(cost_usd), 0) AS cost_usd,"
        " SUM(CASE WHEN injection_verdict = 'block' THEN 1 ELSE 0 END) AS blocked,"
        " SUM(CASE WHEN injection_verdict = 'flag' THEN 1 ELSE 0 END) AS flagged,"
        " SUM(CASE WHEN had_pii = 1 THEN 1 ELSE 0 END) AS with_pii"
        " FROM audit_log GROUP BY key_id ORDER BY requests DESC"
    )
    return [dict(r) for r in rows]
