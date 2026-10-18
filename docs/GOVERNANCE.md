# Governance Charter: Gatehouse

Short on purpose. This is a hackathon build, and the charter should fit on one page.

## Data retention

- Audit rows are kept for 30 days, then deleted. The audit log stores hashes and counts, never raw prompt text, so retention is about incident review, not data hoarding.
- API key records are kept until revoked, then marked revoked and retained for 30 days for incident correlation.
- There is no user data store beyond keys and audit rows. Gatehouse holds no conversations.

## Error ownership

- The gateway operator owns gateway errors: 5xx responses, misconfigured thresholds, expired upstream keys.
- The upstream provider owns model errors: bad completions, hallucinations, upstream outages. Gatehouse surfaces these as 502s with the upstream's message attached.
- The API key holder owns their traffic: prompt content, token spend, and injection attempts made with their key. Per-key stats exist so ownership is visible.

## Human override

- Injection screening is advisory by default configuration choice: set `INJECTION_POLICY=flag` and every suspicious request is logged and passed through for human review via `/admin/audit`.
- Setting `INJECTION_POLICY=block` makes the gateway refuse high-score requests with 403. The matched signals are returned so the decision is explainable.
- Thresholds (`INJECTION_FLAG_SCORE`, `INJECTION_BLOCK_SCORE`) are operator-tunable. If legitimate traffic is blocked, the fix is a config change, not a code change.
- Key revocation is immediate and takes effect on the next request.

## Change control

- Price table changes go through `PRICE_TABLE_JSON` and apply on restart.
- No code change is needed to onboard a new consumer: create a key, set its limits, hand it over.
