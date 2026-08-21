# Phase 02 Exit Criteria

## Gate Checklist
- [x] Authenticated Responses requests forward to the configured backend deployment.
- [x] Authenticated embeddings requests forward to the configured backend deployment.
- [x] Multi-backend pools use documented deterministic highest-weight selection with lexical tie-breaking.
- [x] Unknown models return an OpenAI-compatible 404 without contacting a backend.
- [x] Malformed JSON or missing required fields return a clear 4xx without contacting a backend.
- [x] Client `api-key`, `Authorization`, cookies, hop-by-hop, `Forwarded`, and `X-Forwarded-*` headers are not sent upstream.
- [x] The configured backend credential is sent only to that configured backend.
- [x] Non-streaming upstream JSON and bounded error statuses are passed through safely; transport failures become bounded router errors.
- [x] Streaming responses preserve upstream SSE bytes/event boundaries, close on cancellation, and do not buffer the full response.
- [x] Upstream failures before the first event are returned as HTTP errors; failures after output begins are emitted as SSE error events.
- [x] No retry or failover occurs in this phase.
- [x] Focused and full tests pass with at least 80 percent coverage.
- [x] Ruff, formatting, and strict mypy pass.
- [x] Documentation labels forwarding as implemented and routing/retries/credits as planned.
- [x] `README.md`, `docs/index.md`, `docs/api/index.md`, `docs/features/index.md`, `docs/architecture/solution-structure.md`, `docs/configuration/index.md`, `docs/configuration/security.md`, and `docs/decisions/requirements-traceability.md` reflect the Phase 02 status.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | | Pending | |
| Approver | | Pending | |
