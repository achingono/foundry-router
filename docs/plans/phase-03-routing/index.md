# Phase 03 Health-Aware Routing and Failover

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Implement health-aware backend selection, bounded retries, cooldowns, and single-failover for Responses and embeddings requests. This phase transforms the deterministic forwarding from Phase 02 into a resilient routing layer that classifies upstream failures, applies bounded retries with exponential backoff, enforces cooldown periods after 429/5xx responses with concurrency safety and robust `Retry-After` parsing, and fails over to an alternative backend once per request without retrying after streaming output begins.

## Scope

### In Scope
- Backend health states: `ACTIVE`, `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED` with concurrency-safe `asyncio.Lock` protection
- Failure classification: retryable (429, 500, 502, 503, 504, transport) vs non-retryable (other 4xx)
- Bounded retries with configurable max attempts, exponential backoff, and robust `Retry-After` parsing supporting both integer seconds and HTTP-date formats clamped within `retry_max_delay_seconds`
- Per-backend cooldown tracking with configurable durations and automatic expiration
- Single failover to next-highest-weight healthy backend when first attempt fails with retryable error
- Exhausted cooldown handling: returning `503 Service Unavailable` (or `429` for quota exhaustion) with a `Retry-After` header matching the minimum remaining cooldown time among candidates
- Streaming contract preservation: no retry or failover after meaningful SSE output begins
- Selection excludes backends in cooldown or disabled when healthy alternatives exist (unless emergency fallback is enabled)
- All routing logic stays in the API layer; backend client remains a safe HTTP seam

### Out of Scope
- Credit-aware routing, safety reserves, cycle urgency, or cost reconciliation
- Weighted round-robin on equal scores (remains lexicographically smallest backend ID)
- Persistent or externally reconciled usage/cost state
- Metrics, dashboards, Application Insights, or Prometheus exposition
- Infrastructure, deployment, or real Azure integration tests
- Chat Completions compatibility

## Entry Criteria
- Phase 02 forwarding hardening is merged and its verification gates pass.
- Backend endpoints, credentials, model pools, deployments, and API versions are supplied through validated configuration.
- Phase 03 plan has received independent review.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer