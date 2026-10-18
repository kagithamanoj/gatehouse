"""Token cost estimation from a configurable per-model price table."""

from __future__ import annotations


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int,
                      price_table: dict) -> float:
    """Cost in USD. Unknown models are treated as unpriced (0.0)."""
    prices = price_table.get(model)
    if not prices:
        return 0.0
    per_input = float(prices.get("input", 0.0)) / 1_000_000
    per_output = float(prices.get("output", 0.0)) / 1_000_000
    return round(prompt_tokens * per_input + completion_tokens * per_output, 6)


def estimate_tokens(text: str) -> int:
    """Rough token estimate used when the upstream reports no usage."""
    if not text:
        return 0
    return max(1, int(len(text.split()) * 1.33))
