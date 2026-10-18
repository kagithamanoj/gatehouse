# Threat Model: Gatehouse

Scope: the gateway itself and the traffic passing through it. The upstream LLM provider is treated as semi-trusted: it is expected to be honest but it must never receive PII it does not need.

## Threat matrix

| Threat | Impact | Mitigation in Gatehouse | Residual risk |
|---|---|---|---|
| Prompt injection / jailbreak in user input | Model misbehavior, data exfiltration via the model, policy bypass | Heuristic scanner scores every prompt (instruction-override, jailbreak terms, prompt-extraction, role-override, hidden unicode, obfuscation). Policy `block` returns 403; `flag` lets it through but marks it. Every verdict is audited. | Heuristics are not complete. Novel phrasing and multi-turn attacks can slip past. This is a first-pass filter, not a proof. |
| PII exfiltration via prompts | Customer PII sent to a third-party API, regulatory exposure | Regex redaction of emails, phones, SSNs, and Luhn-validated cards runs on every prompt before the upstream call. The upstream only ever sees redacted text. | Regex misses unusual formats and non-US identifiers. Structured data (JSON blobs, base64) is scanned as text only. |
| PII leak via completions | Model echoes or hallucinates PII back to the caller | Same redaction pass runs on every completion before the response is returned. | Same format limits as above. A model that paraphrases PII (e.g. spelling out digits) will not match. |
| API key theft / sharing | Unauthorized spend, abuse under someone else's identity | Keys are random 256-bit tokens stored as SHA-256 hashes, verified in constant time. Admins can revoke instantly. Plaintext is shown once at creation. | A stolen key works until revoked. There is no IP binding or key rotation schedule in v1. |
| DoS via token burn | Runaway cost from a bug, a loop, or a malicious client | Per-key token bucket rate limiting (configurable RPM and burst, overridable per key). 429s carry Retry-After. | Limits are per key, not per IP, and buckets live in memory, so a restart resets them. Distributed abuse across many keys is not correlated. |
| Upstream compromise or outage | Malicious or broken upstream responses reaching clients | Completions are re-scanned for PII, failures map to 502 without leaking internals, and the audit log records the error. | Gatehouse does not validate upstream content for correctness or malice beyond PII. |
| Audit log tampering | Loss of the incident record | SQLite file with append-only writes from the gateway process. Raw prompts are never stored, only SHA-256 hashes, so the log itself is not a PII store. | Anyone with filesystem access to the DB file can read or alter it. No append-only enforcement at rest in v1. |
| Admin key exposure | Full key management and audit visibility to an attacker | Admin auth is a separate key from user keys, never logged, never returned by any endpoint. | The default `changeme-admin-key` must be replaced in any real deployment. This is documented in `.env.example` and the README. |

## Trust boundaries

1. Client to gateway: untrusted. Authenticated by API key, rate limited, scanned.
2. Gateway to upstream: semi-trusted. Receives redacted prompts only.
3. Admin endpoints: trusted operator only, separate credential.
4. Audit store: trusted for reads by the operator, write-only from the gateway.

## Out of scope for v1

Multi-turn conversation tracking, semantic PII detection, per-IP limits, key rotation, encrypted audit storage, and upstream content validation. Each is a reasonable next step and is noted here so nobody mistakes v1 for a finished security product.
