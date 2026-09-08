# Phase 08 Credit-Integrity and Boundary Hardening

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Close the correctness, trust-boundary, resource-economics, and operability gaps identified by the deep review of the implemented router. This phase decouples client-supplied identifiers from internal credit accounting, bounds request intake, makes credit and pricing misconfiguration fail loudly at startup rather than silently at request time, and prevents inflight-credit leaks. It does not add new runtime features; it hardens the existing configuration, API, forwarding, routing, and credit boundaries so the credit-aware routing core cannot be corrupted or silently disabled.

## Scope
This phase is a remediation phase. Every change is local to an existing boundary and is accompanied by tests and documentation updates. No new endpoints, no infrastructure, and no distributed state are introduced.

## In Scope
- Decouple the client `x-request-id` correlation ID from the internal reservation/finalization key (Critical finding F1).
- Enforce a bounded maximum request body size before JSON parsing and bound token-estimation recursion depth (Major finding F2).
- Add a startup/readiness invariant so every routable backend has complete credit configuration and every configured model has pricing (Major finding F3).
- Add reservation age tracking plus a lazy/periodic reaper and admin visibility so inflight credit cannot leak on client disconnects (Major finding F4).
- Harden `parse_retry_after` against non-ASCII digit headers (Suggestion F5).
- Remove redundant per-request `sync_from_settings` work on the hot path (Suggestion F6).
- Reduce per-event JSON parsing cost in the streaming usage extractor (Suggestion F7).
- Remove auth key-position timing short-circuit (Suggestion F8).
- Update tests, requirements traceability, security, observability, and status documentation to reflect the verified changes.

## Out of Scope
- Distributed / multi-replica credit accounting (remains `Planned`; only documented as a scaling boundary here).
- New routing algorithms, new health signals, or new backend operations.
- Infrastructure provisioning, CI/CD topology changes, or real Azure integration tests.
- Any change to the streaming/SSE event-boundary contract or the "never retry after output begins" rule.

## Entry Criteria
- The implemented tree matches the modules referenced in [Inputs](inputs.md).
- The deep-review findings (F1–F8) are accepted as the work item source.
- The repository virtual environment `.venv/` is available for verification.
- No real credentials or Azure resource identifiers are required for verification.

## Exit Criteria
See [Exit Criteria](exit-criteria.md).

## Roles
- Owner: Implementation agent
- Reviewer: Independent planning/second-model review
- Approver: Project maintainer
