# Phase 04 Exit Criteria

## Gate Checklist
- [ ] Cycle calculations pass tests for start days 1 and 20, month lengths, February, leap years, and month/year boundaries.
- [ ] Request estimates are conservative, finite, non-negative, pricing-driven, and explicitly labeled as estimates.
- [ ] Supported Responses and embeddings request shapes, text-token bound, output-token bound, unsupported content, missing pricing, zero pricing, and invalid estimates have deterministic documented behavior and tests.
- [ ] Effective safety reserves and spendable credit are calculated correctly; usable credit is clamped at zero.
- [ ] Every credit-aware backend has a validated local estimated cycle allowance and remaining-credit initialization; missing values fail closed and are never represented as authoritative Azure balances.
- [ ] Reserve-percent semantics use the configured estimated cycle allowance as denominator consistently in code and documentation.
- [ ] Concurrent reservations cannot oversubscribe a backend's spendable estimated credit.
- [ ] Reservations are reused across retries on the same backend; on failovers to a new backend, the upstream reservation is released and re-reserved on the target backend; and released exactly once on success, upstream error, stream completion/abort, disconnect, or cancellation.
- [ ] Protected or insufficient-capacity candidates are not intentionally selected; safe-capacity exhaustion returns `503 Service Unavailable` with `insufficient_credit_capacity` without contacting a backend or leaking internal state.
- [ ] Credit-aware selection is model-specific, explainable, compatible with arbitrary backend counts, and preserves health/cooldown precedence.
- [ ] ADR-006 score components, default weights, state precedence, and equal-score weighted selection are implemented and tested, or any deferral is approved and documented before closure.
- [ ] Existing retry, single-failover, streaming no-retry-after-output, correlation, and credential-isolation tests still pass.
- [ ] No implementation presents local estimates as authoritative Azure balances or claims reconciliation is implemented.
- [ ] Focused and full tests pass with at least 80% coverage for implemented code.
- [ ] Ruff, formatting, type checking, and applicable Docker/quality verification pass.
- [ ] Documentation, requirements traceability, and evidence identify remaining distributed-state and reconciliation work as Planned.
- [ ] Phase 03 routing/hardening approval or maintainer waiver is recorded before implementation begins.
- [ ] Conditional SonarQube, deep-review, documentation-link, secret-scan, and final-diff checks required by `AGENTS.md` are run when applicable.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | Implementation agent | Pending | |
| Reviewer | Independent review session | Pending | |
| Approver | Project maintainer | Pending | |
