"""In-memory per-key token bucket rate limiter."""

from __future__ import annotations

import threading
import time


class TokenBucketLimiter:
    def __init__(self):
        self._buckets: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _refill(self, bucket: dict, now: float, rpm: float, burst: float) -> None:
        elapsed = max(0.0, now - bucket["updated"])
        bucket["tokens"] = min(burst, bucket["tokens"] + elapsed * (rpm / 60.0))
        bucket["updated"] = now

    def allow(self, key_id: str, rpm: float, burst: float) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key_id)
            if bucket is None:
                bucket = {"tokens": float(burst), "updated": now}
                self._buckets[key_id] = bucket
            self._refill(bucket, now, rpm, burst)
            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return True, 0.0
            deficit = 1.0 - bucket["tokens"]
            retry_after = deficit / (rpm / 60.0) if rpm > 0 else 60.0
            return False, retry_after

    def reset(self, key_id: str | None = None) -> None:
        with self._lock:
            if key_id is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key_id, None)
