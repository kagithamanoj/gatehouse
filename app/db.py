"""SQLite storage for API keys and the audit log."""

from __future__ import annotations

import sqlite3
import threading


SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    key_id     TEXT PRIMARY KEY,
    key_hash   TEXT NOT NULL,
    name       TEXT NOT NULL,
    rpm        INTEGER,
    burst      INTEGER,
    created_at TEXT NOT NULL,
    revoked    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT NOT NULL,
    key_id           TEXT NOT NULL,
    model            TEXT,
    prompt_tokens    INTEGER,
    completion_tokens INTEGER,
    latency_ms       REAL,
    injection_verdict TEXT,
    injection_score  REAL,
    redactions       TEXT,
    cost_usd         REAL,
    prompt_sha256    TEXT,
    had_pii          INTEGER,
    upstream_mode    TEXT,
    error            TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_key ON audit_log(key_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self):
        with self._lock:
            self._conn.close()
