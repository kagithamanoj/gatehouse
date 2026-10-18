"""Heuristic prompt-injection scanner.

Scores message text against weighted jailbreak / instruction-override patterns
plus structural obfuscation signals. Produces allow | flag | block verdicts.
This is a first-pass filter, not a guarantee; see docs/THREAT_MODEL.md.
"""

from __future__ import annotations

import re

# (compiled pattern, weight, label)
_PATTERNS: list[tuple[re.Pattern, float, str]] = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I), 55, "instruction-override"),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.I), 40, "instruction-override"),
    (re.compile(r"\bjailbreak\b", re.I), 30, "jailbreak-term"),
    (re.compile(r"do anything now", re.I), 25, "dan-pattern"),
    (re.compile(r"reveal your (system prompt|instructions)", re.I), 40, "prompt-extraction"),
    (re.compile(r"\bsystem prompt\b", re.I), 15, "prompt-extraction"),
    (re.compile(r"bypass (your|all|the) (safety|polic|guideline|filter|restriction)", re.I), 25, "safety-bypass"),
    (re.compile(r"override (your|all|the) (safety|polic|guideline|filter|restriction)", re.I), 25, "safety-bypass"),
    (re.compile(r"you are now\b", re.I), 20, "role-override"),
    (re.compile(r"pretend (you are|to be)", re.I), 20, "role-override"),
    (re.compile(r"act as if you (have no|were not)", re.I), 20, "role-override"),
    (re.compile(r"as an? (unfiltered|uncensored)", re.I), 20, "role-override"),
    (re.compile(r"no (safety|ethical|moral) (constraints|limits|restrictions)", re.I), 20, "safety-bypass"),
    (re.compile(r"\bdeveloper mode\b", re.I), 15, "role-override"),
    (re.compile(r"repeat after me\s*:", re.I), 10, "echo-attack"),
]

_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\ufeff]")
_BLOB = re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b")


def scan(text: str, flag_score: float = 25.0, block_score: float = 50.0,
         policy: str = "block") -> dict:
    """Scan text. Returns {score, matched, verdict} with verdict in allow|flag|block."""
    text = text or ""
    score = 0.0
    matched: list[str] = []

    for pattern, weight, label in _PATTERNS:
        if pattern.search(text):
            score += weight
            if label not in matched:
                matched.append(label)

    if _ZERO_WIDTH.search(text):
        score += 25
        matched.append("hidden-unicode")

    if len(text) > 60:
        special = sum(1 for ch in text if not (ch.isalnum() or ch.isspace()))
        if special / len(text) > 0.45:
            score += 20
            matched.append("obfuscated-tokens")

    if _BLOB.search(text):
        score += 15
        matched.append("encoded-blob")

    verdict = "allow"
    if score >= block_score:
        verdict = "block"
    elif score >= flag_score:
        verdict = "flag"

    if verdict == "block" and policy == "flag":
        verdict = "flag"

    return {"score": round(score, 1), "matched": matched, "verdict": verdict}
