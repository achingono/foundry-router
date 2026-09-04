# Phase 04 Credit-Aware Scheduling

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Implement the first safe credit-aware scheduling layer for configured backend pools. The phase will calculate backend credit-cycle windows, estimate request cost from configured model pricing, reserve conservative request cost before dispatch, release reservations on every completion path, and classify candidates as usable, conservation, or protected without confusing local estimates with authoritative Azure balances. Because reconciliation is out of scope, each backend will require an explicitly configured local estimated cycle allowance and remaining balance; these values are initialization estimates, not Azure balances. The existing health, quota, retry, failover, streaming, authentication, and backend allow-list behavior must remain intact.

## Scope

### In Scope
- A feature-local credit subsystem with pure cycle and pricing calculations.
- Per-backend cycle start-day handling across month boundaries, February, leap years, and year boundaries.
- Per-backend configured estimated cycle allowance and remaining-credit initialization, with explicit behavior for missing or stale local estimates.
- Conservative input and expected-output token/cost estimation for Responses and embeddings requests.
- Effective safety-reserve calculation from configured dollar and percentage minimums.
- Concurrent in-memory reservations keyed by request ID, with atomic reserve/release operations.
- Candidate filtering and explainable credit state: usable, conservation, protected, or insufficient capacity.
- Credit-aware routing selection for model-specific backend pools while preserving health/cooldown filtering and deterministic tie-breaking.
- Explicit safe-capacity errors when no candidate can accept the conservative reservation.
- Unit, integration, concurrency, streaming-cleanup, and negative-estimate tests.
- Documentation and traceability updates that label local values as estimates.

### Out of Scope
- Azure Cost Management or other authoritative usage/cost reconciliation.
- Azure Table Storage shared state; Redis is an optional later cache under ADR-005.
- Multi-replica credit correctness or enabling `max_replicas > 1`.
- Metrics dashboards, Application Insights, infrastructure, or deployment changes.
- Dynamic pricing discovery, model aliases, chat completions, or new public endpoints.
- Replacing health-aware retry/failover or retrying after meaningful streaming output.

## Entry Criteria
- Phase 03 routing and hardening gates pass, including streaming cleanup and bounded retry behavior.
- Existing configuration exposes validated pricing, reserve, cycle-start-day, and reconciliation-interval fields; Phase 04 adds validated per-backend local credit estimates and documents whether cycle-start-day values are required for every backend.
- The current model/backend pool and backend health seams are identified and covered by tests.
- The Phase 03 routing and hardening plans have maintainer approval, or an explicit maintainer waiver is recorded.
- The Phase 04 plan has received independent review.
- The single-replica limitation for in-memory credit state is documented and accepted for this phase.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent review session
- Approver: Project maintainer
