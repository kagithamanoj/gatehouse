# AI System Card: Gatehouse

## What it is

Gatehouse is a policy-enforcement proxy for LLM traffic. It does not train models, fine-tune models, or make autonomous decisions with model output. It screens, redacts, logs, and meters requests passing between client applications and an upstream LLM.

## Intended use

- Teams that call LLM APIs from production services and need auth, rate limits, PII protection, injection screening, auditability, and cost tracking in one place.
- Demos and hackathons: mock upstream mode runs with no API key and deterministic responses.

## Not intended for

- Regulated workloads that need certified controls (HIPAA, PCI-DSS scope, etc.). The PII redaction is regex-based and best-effort; see Threat Model.
- Fully autonomous agentic loops with no human review. The injection scanner is heuristic.

## Models

Gatehouse is model-agnostic. In `mock` mode it returns deterministic demo responses without calling any model. In `openai` mode it forwards to any OpenAI-compatible `/v1/chat/completions` endpoint. The price table ships with common OpenAI model prices and accepts overrides; unknown models are treated as unpriced (cost 0.0) rather than guessed.

## Data handling

- Prompts are scanned and redacted in memory, then the redacted form is sent upstream.
- The audit log stores: timestamp, key id, model, token counts, latency, injection verdict and score, redaction counts, cost, a SHA-256 hash of the prompt, and whether PII was present. Raw prompt text is never written to disk.
- API keys are stored as SHA-256 hashes. Plaintext is returned once at creation.
- Retention policy: 30 days for audit rows (see GOVERNANCE.md).

## Limitations

- Injection detection is pattern-based and will miss novel attacks. It will also occasionally flag legitimate text that resembles attack phrasing.
- PII detection covers common US formats for emails, phones, SSNs, and credit cards. It does not cover every identifier type or every country format.
- Rate limiter state is in memory and resets on restart.
- Cost estimates depend on token counts reported by the upstream (or a word-based estimate in mock mode) and on the configured price table. Treat them as estimates, not invoices.

## Human override

- Injection policy can be set to `flag` instead of `block` so a human reviews flagged traffic via `/admin/audit` before deciding.
- Blocked requests return 403 with the matched signals, so operators can tune thresholds (`INJECTION_FLAG_SCORE`, `INJECTION_BLOCK_SCORE`) against real traffic.
- Keys can be revoked instantly. The admin key is separate from user keys.
