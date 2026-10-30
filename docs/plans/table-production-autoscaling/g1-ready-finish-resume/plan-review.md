# G1 resume amendment — independent plan review

Date: 2026-10-30. Reviewer: independent OpenCode session, separate from the
continuation author. Reviewed the [inputs](inputs.md),
[activities](activities.md), [outputs](outputs.md),
[exit criteria](exit-criteria.md), [risk register](risk-register.md),
[evidence](evidence.md), original G1 finish plan/packet, and the private
case-2 read-only reconciliation.

## Verdict

**Approved for implementation only. Unresolved Critical: 0. Unresolved Major: 0.**
This review is not implementation review, exact private-packet approval, or
execution approval.

## Review findings

- The partial apply is treated as consumed; cases 0/1 remain accepted, case 2
  is not replayed and is accepted only through its response/usage plus
  same-process Table balance/debit reconciliation, and case 3 remains the sole
  unstarted original slot.
- The continuation adds no allocation, budget, retry, provider, image/table/
  role/seed/pool mutation, or executor Allow. It preserves the original
  one-case slot bound, reserves only the original final DENY attempt, and
  permits at most one restart after full success.
- A durable global continuation marker begins the authorized post-approval
  boundary before dynamic preflight. Every subsequent refusal/failure routes
  through exactly one exclusive DENY attempt; an ambiguous acknowledgement is
  not retried. Approval/lock failure before ownership remains non-mutating.
- Continuation-wide and nested deadlines include dispatch, DENY propagation,
  drain, restart observation, and cleanup headroom. Focused tests explicitly
  cover pre-dispatch refusal, dispatch failure, ambiguous DENY, fresh-directory
  replay, and pre-boundary approval/lock failure.
- Restart remains success-only after exact settlement, live 403, and quiet
  drain. Production remains outside the amendment.

No code, tests, Azure/provider requests, or mutations were performed by the
reviewer. Fresh implementation checks, contextual review, exact private-packet
review, and independent exact execution approval remain mandatory.

## Final ordering clarification — re-approved

A subsequent independent plan re-review confirmed the final ordering: Step 2 is
strictly pre-approval read-only packet preparation; after exact approval and
ownership locks, the apply path durably consumes the global continuation marker
before all execution-time history/slot/process/finance/configuration/topology
checks. Those checks are inside the DENY-on-every-exit path. The DENY marker is
separate and is consumed immediately before its one PATCH. No Critical or Major
findings remain. The reviewer made no code changes, tests, cloud requests, or
mutations; exact execution approval remains pending.
