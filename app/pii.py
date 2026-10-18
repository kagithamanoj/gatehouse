"""PII redaction for prompts and completions.

Covers emails, US phone numbers, SSNs, and credit card numbers (Luhn-checked
to keep false positives down). Returns the redacted text plus per-type counts.
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ \-.]*?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0 and len(digits) >= 13


def _redact_cards(text: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            count += 1
            return "[REDACTED:CARD]"
        return match.group(0)

    return CARD_CANDIDATE_RE.sub(repl, text), count


def redact(text: str) -> tuple[str, dict]:
    """Redact PII in text. Returns (redacted_text, {"EMAIL": n, ...})."""
    if not text:
        return text, {}
    counts: dict[str, int] = {}

    # Cards first (Luhn-checked) so phone/SSN patterns cannot match inside them.
    text, n = _redact_cards(text)
    if n:
        counts["CARD"] = n

    text, text_before = SSN_RE.subn("[REDACTED:SSN]", text)
    if text_before:
        counts["SSN"] = text_before

    text, text_before = PHONE_RE.subn("[REDACTED:PHONE]", text)
    if text_before:
        counts["PHONE"] = text_before

    text, text_before = EMAIL_RE.subn("[REDACTED:EMAIL]", text)
    if text_before:
        counts["EMAIL"] = text_before

    return text, counts


def merge_counts(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + v
    return out
