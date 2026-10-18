# AI Usage Declaration

This project was built with AI coding assistance, and we are stating that plainly.

- **Tool used:** Muse, an AI agent by Meta, working under the direction of the project owner.
- **What the AI did:** scaffolded the repository, wrote the initial implementation of all modules, wrote the test suite, wrote this documentation, and ran the tests to green.
- **What the owner did:** defined the product, the feature set, the threat model scope, and the acceptance bar (all tests passing, honest docs, no hidden content). The owner reviews the code before any demo or submission.
- **Review status:** every module was executed by the test suite (40 tests passing). No AI-generated content in this repo is hidden or misrepresented as hand-written.
- **Upstream behavior:** in mock mode the gateway returns deterministic demo text written by the developers, clearly labeled as mock. In live mode it forwards to a real LLM endpoint chosen by the operator; model outputs are the upstream provider's, screened by Gatehouse's PII redaction before delivery.

Nothing in this repo claims capabilities it does not have. Where a control is best-effort (regex PII detection, heuristic injection screening), the docs say so.
