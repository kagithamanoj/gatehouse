"""API key issuance and verification. Keys are stored as SHA-256 hashes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def create_key(db, name: str, rpm: int | None = None, burst: int | None = None) -> dict:
    key_id = "key_" + uuid.uuid4().hex[:12]
    plaintext = "gatehouse_" + secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO api_keys (key_id, key_hash, name, rpm, burst, created_at, revoked)"
        " VALUES (?, ?, ?, ?, ?, ?, 0)",
        (key_id, hash_key(plaintext), name, rpm, burst, _utcnow()),
    )
    return {"key_id": key_id, "api_key": plaintext, "name": name, "rpm": rpm, "burst": burst}


def verify_key(db, plaintext: str) -> dict | None:
    if not plaintext:
        return None
    candidate = hash_key(plaintext)
    rows = db.query(
        "SELECT key_id, key_hash, name, rpm, burst, created_at, revoked FROM api_keys"
    )
    for row in rows:
        if hmac.compare_digest(row["key_hash"], candidate):
            if row["revoked"]:
                return None
            return dict(row)
    return None


def list_keys(db) -> list[dict]:
    rows = db.query(
        "SELECT key_id, name, rpm, burst, created_at, revoked FROM api_keys ORDER BY created_at"
    )
    return [dict(r) for r in rows]


def revoke_key(db, key_id: str) -> bool:
    cur = db.execute("UPDATE api_keys SET revoked = 1 WHERE key_id = ?", (key_id,))
    return cur.rowcount > 0
