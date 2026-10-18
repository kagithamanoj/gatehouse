"""Configuration loaded from environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


DEFAULT_PRICE_TABLE = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "mock-llm": {"input": 0.00, "output": 0.00},
}


@dataclass
class Settings:
    upstream_mode: str = "mock"  # mock | openai
    upstream_base_url: str = "https://api.openai.com/v1"
    upstream_api_key: str = ""
    upstream_timeout_s: float = 60.0
    default_model: str = "mock-llm"
    admin_api_key: str = "changeme-admin-key"
    db_path: str = "./gatehouse.db"
    rate_limit_rpm: int = 60
    rate_limit_burst: int = 10
    injection_policy: str = "block"  # block | flag
    injection_flag_score: float = 25.0
    injection_block_score: float = 50.0
    redact_completions: bool = True
    price_table: dict = field(default_factory=lambda: dict(DEFAULT_PRICE_TABLE))


def _getenv_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def load_settings() -> Settings:
    price_table = dict(DEFAULT_PRICE_TABLE)
    raw_prices = os.getenv("PRICE_TABLE_JSON")
    if raw_prices:
        try:
            overrides = json.loads(raw_prices)
            for model, prices in overrides.items():
                price_table[model] = {
                    "input": float(prices.get("input", 0.0)),
                    "output": float(prices.get("output", 0.0)),
                }
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            pass

    return Settings(
        upstream_mode=os.getenv("UPSTREAM_MODE", "mock").strip().lower(),
        upstream_base_url=os.getenv("UPSTREAM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        upstream_api_key=os.getenv("UPSTREAM_API_KEY", ""),
        upstream_timeout_s=float(os.getenv("UPSTREAM_TIMEOUT_S", "60")),
        default_model=os.getenv("DEFAULT_MODEL", "mock-llm"),
        admin_api_key=os.getenv("ADMIN_API_KEY", "changeme-admin-key"),
        db_path=os.getenv("DB_PATH", "./gatehouse.db"),
        rate_limit_rpm=int(os.getenv("RATE_LIMIT_RPM", "60")),
        rate_limit_burst=int(os.getenv("RATE_LIMIT_BURST", "10")),
        injection_policy=os.getenv("INJECTION_POLICY", "block").strip().lower(),
        injection_flag_score=float(os.getenv("INJECTION_FLAG_SCORE", "25")),
        injection_block_score=float(os.getenv("INJECTION_BLOCK_SCORE", "50")),
        redact_completions=_getenv_bool("REDACT_COMPLETIONS", True),
        price_table=price_table,
    )
