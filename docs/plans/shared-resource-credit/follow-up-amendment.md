# Remaining Major findings — approved follow-up

## Status: Approved; Implemented (local verification passed)

The operator approved these three fixes under the existing reviewed failure contract before edits.
No additional policy question or plan-review session is required. No production deployment, commit,
or operator-local input changes are authorized.

1. **Failed membership initialization:** Table sync must raise a typed credit-store error whenever
   initialization/config merge is incomplete. Retain old published membership and all attempted
   partitions for recovery, but never dispatch new Settings through that old map after a failed
   sync. Do not cache failed Settings; retry the same object after recovery. Regression: changed
   membership plus failed initialization causes zero egress, then the same Settings succeeds.
2. **Retiring stale tracked owners:** periodically reconcile the bounded tracked-ID set against
   complete ownership discovery of every known partition. Retire only confirmed absence/finalization;
   do not infer absence from failed/incomplete reads or evict pending/ambiguous IDs at capacity.
   Run this maintenance independently of authoritative balance-provider availability. Cover timeout
   before commit, other-writer recovery, reaper commit with lost acknowledgement, and incomplete
   discovery preserving capacity constraints.
3. **Post-output failed streams:** stream_response is called after meaningful first output. Known
   usage wins; absent usage must settle full reserved cost even on HTTPError/cancellation. A stream
   error must never persist a zero settlement intent merely because status became 502. Confirmed
   pre-egress/rejected-request release remains zero. Update the old opposite test expectation and
   verify balances and inflight cleanup in memory/Table, preserving SSE and no failover.

Run focused faults, full suite with Azurite, coverage >=80%, Ruff/format/mypy, Docker build, contextual
review, relative documentation links and final diff. Update recovery docs, traceability and exact
evidence; no production claims. Independent implementation re-review may follow.

Completed verification: **444 tests**, **90.14% coverage**, all **14 Azurite tests**, quality checks
and Docker build passed. See [follow-up evidence](follow-up-evidence.md).
