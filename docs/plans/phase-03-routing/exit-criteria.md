# Phase 03 Exit Criteria

## Gate Checklist
- [x] Upstream 429 responses place the backend in `QUOTA_COOLDOWN` and trigger failover to a healthy alternative.
- [x] Upstream 500/502/503/504/transport errors place the backend in `ERROR_COOLDOWN` and trigger failover.
- [x] Retry loop respects `retry_attempts`, exponential backoff, `Retry-After` header, and `retry_max_delay_seconds`.
- [x] `Retry-After` header parsing correctly handles both integer seconds and HTTP-date formats, clamped between 0 and `retry_max_delay_seconds`.
- [x] Backend health and cooldown state mutations are concurrency-safe using an `asyncio.Lock`.
- [x] When all candidate backends are in cooldown, the router returns `503 Service Unavailable` (or `429` for quota exhaustion) with a `Retry-After` header matching the minimum remaining cooldown time among candidates.
- [x] No retry or failover occurs after the first SSE chunk has been yielded to the client.
- [x] Backend selection excludes `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, and `DISABLED` backends when healthy alternatives exist.
- [x] `protected_emergency_fallback` allows routing to a cooled backend only when it is the sole candidate.
- [x] Client `api-key`, `Authorization`, cookies, hop-by-hop, and `X-Forwarded-*` headers are never sent upstream; only the selected backend's credential is injected.
- [x] Correlation ID is propagated to each upstream attempt.
- [x] Focused and full tests pass with at least 80% coverage.
- [x] Ruff, formatting, and strict mypy pass.
- [x] Documentation labels health-aware routing/retry/failover as implemented and credit/cost/metrics as planned.
- [x] `README.md`, `docs/index.md`, `docs/api/index.md`, `docs/features/index.md`, `docs/architecture/solution-structure.md`, `docs/configuration/index.md`, `docs/configuration/security.md`, and `docs/decisions/requirements-traceability.md` reflect the Phase 03 status.

## Approval Table

| Role | Name | Status | Notes |
|---|---|---|---|
| Owner | Implementation Agent | Completed | Phase 03 implementation and test suite complete |
| Reviewer | Independent Review Session | Approved | Health-aware routing, retry/cooldown, failover, concurrency safety, and streaming contract reviewed & verified |
| Approver | Project Maintainer | Approved | Ready for promotion and merge |
