# Contextual Implementation Review

## Scope and provenance

Performed in the implementing session on 2026-10-04 using
[the contextual deep-review prompt](../../../.agents/prompts/deep-review.prompt.md).
The operator supplied an approved plan with reviewed contract clarifications and requested that
independent implementation review follow this session. This review is not that independent review.
The repository has no `scripts/quality/sonarqube-scan.sh`; no Sonar scan was run.

## Findings addressed

### Major — Table pending-row parsing and failure acknowledgement

- **File/Module:** `state/table.py`, routing release/settlement callers.
- **Issue:** Existing forgiving numeric parsing converted malformed reservation cost to zero;
  exhausted/failed finalization could return success, allowing second egress or lost charges.
- **Why static analysis misses it:** Requires understanding financial ownership and caller transitions.
- **Impact:** Under-reservation, orphaned rows or failover without confirmed release.
- **Fix:** Strict pending/balance decoding, typed finalization read/write/conflict failures, hard-stop
  routing and no free cleanup after attempted settlement. Malformed/outage/conflict tests pass.

### Major — Cleanup dependencies and stream cancellation ordering

- **File/Module:** `api/common.py`, `forwarding/`, `routing/`.
- **Issue:** Credit error prevented quota/metrics cleanup; quota admission exceptions could orphan
  credit; inspecting usage after yielding could miss delivered terminal usage on cancellation.
- **Why static analysis misses it:** Async generator suspension and subsystem cleanup intent.
- **Impact:** Quota reservations leak or settlement loses known usage after disconnect.
- **Fix:** Independent finally cleanup, quota admission exception/cancellation release, inspect bytes
  before unchanged pass-through. Explicit cancellation/settlement-failure tests verify outcomes.

### Major — Live membership and reconciliation ambiguity

- **File/Module:** `credit_groups.py`, both stores and Settings.
- **Issue:** Alias chaining, conflicting aliases and mutable Settings fast paths could redirect ownership.
- **Why static analysis misses it:** Namespace relationships and cross-model credit semantics.
- **Impact:** Wrong account debited or duplicated reconciliation updates.
- **Fix:** One-pass alias resolution, collision/mixed-metering rejection, captured request ownership,
  pending-row guards even on same Settings membership mutation, normalize before any writes and
  coalesce equal/reject conflicting amounts. Memory/Table and other-writer regressions pass.

## Operational boundaries

No runtime guard is a distributed configuration migration protocol. All writers must be drained
before membership changes, especially across restart; no implicit old-partition aggregation exists.
Reconciliation is atomic per account, not across accounts; failures are reported as failed attempts.
Account-level gauges are unique within a scrape; multi-worker metrics aggregation remains Planned.
Production load, real shared-account inference and production cut-over remain unverified.

The subsequent independent review identified five Major findings missed by this scoped contextual
review: free expiry after failed settlement, ambiguous Table admission acknowledged as rejection,
metering/membership synchronization, cross-group request identity races, and stream context-close/
cancellation cleanup. The recovery plan was independently approved in session
`ses_ef6422f4effeLjrO87PAowPxJu` before fixes. All five fixes and fault verification are complete as
recorded in [recovery evidence](recovery-evidence.md). Independent implementation re-review remains
pending; plan approval is not implementation approval.

Subsequent independent review found three remaining Majors: retained old aliases allowed dispatch
after incomplete new-group sync; stale/uncertain owner tracking was not periodically retired after
confirmed external recovery/absence; post-output HTTPError without usage still settled zero. The
operator approved [the follow-up](follow-up-amendment.md) under the reviewed failure contract.
These three fixes and real fault verification are complete in [follow-up evidence](follow-up-evidence.md).
Independent implementation re-review is not claimed by this implementing-session record.
