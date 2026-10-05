# Recovery amendment — independent Major findings

## Status: Approved; Implemented (local verification passed)

This amendment supersedes the original free-expiry recovery policy. The independent implementation
review reported five Major findings; the previous implementing-session review did not detect them.
No production deployment, commit, or operator-local input edit is authorized.

## Proposed financial contract

Use the minimal conservative policy: every expired pending reservation, including legacy rows,
is settled for its full reserved estimate unless a valid, durable settlement intent is available.
An explicit confirmed pre-egress/rejected-request release still charges zero. Mere age is never
evidence that no provider work occurred. This changes memory and Table expiry behavior and can
overestimate spend for abandoned pre-egress requests; subsequent reconciliation can correct it.
Memory remains process-local and loses recovery state on restart as documented.

Before attempting final settlement, retain the intended charge in the memory reservation or persist
it in the Table reservation with an ETag-guarded write. Successful intent persistence followed by
failed balance settlement allows recovery to use known actual cost. If intent persistence itself
fails or has an ambiguous outcome, leave the original conservative reservation recoverable and
raise a typed failure. Never substitute a free release. Validate intent strictly and never overwrite
a previously confirmed settlement intent with a release. Recovery and finalization must guard both
reservation and balance ETags, so concurrent intent writes, reapers and finalizers cannot lose a
charge or double-debit. Confirmed absence/finalization remains idempotent.

## Five fixes

1. **Financial recovery:** conservative expiry in both stores; durable/retained known settlement
   intent where feasible; fault tests run failed settlement through recovery and check debit,
   inflight capacity, idempotency, and restart behavior.
2. **Ambiguous admission:** Table transaction exceptions (including commit then timeout) raise
   typed store failure and stop candidate selection. False means confirmed non-admission only.
   Conflicts can retry only after fresh confirmation; exhausted/unconfirmed outcomes fail closed.
   Preserve captured possible ownership on ambiguous attempts for recovery; no alternate egress.
3. **Membership serialization:** include metering in the membership fingerprint. Serialize local
   sync with admission and resolve published aliases under that protection. Publish membership
   only after validating old pending ownership. Retain old partitions as discoverable for recovery
   until drained; do not silently drop them after a metering flip or failed sync. Support mapping
   and object configuration stubs. All-writer drained rollout remains mandatory across replicas.
4. **Request identity:** memory cross-group assignment of an existing request ID raises until
   confirmed release. Table local request-identity locking prevents simultaneous cross-partition
   creation; use bounded active/uncertain ownership tracking, retired safely only after confirmed
   absence/finalization. Check discoverable partitions when ownership is unknown; multiple owners
   are a typed ambiguity, never pick the first. Server-owned unique IDs remain required across
   replicas; no new unbounded per-ID lock cache or cross-partition implicit transfer.
5. **Streaming cleanup:** run context close, credit settlement, quota cleanup and telemetry as
   independent steps even when context close raises. Execute financial cleanup in a shielded,
   bounded task; repeated caller cancellation must not cancel settlement. Preserve and propagate
   actionable failures, cancel and await timed-out cleanup tasks, and never detach unbounded work.
   Deadline exhaustion leaves conservative durable recovery, not a free release. Preserve SSE
   bytes and no-failover-after-output semantics.

## Required fault reproductions and verification

- Failed settlement followed by expiry: known charge retained when persisted, conservative reserved
  charge otherwise; legacy expired rows charged; no duplicate charge across recovery/finalization.
- Reservation commit followed by TimeoutError: one reservation only, typed failure, zero subsequent
  candidate selection/egress; outage/conflict exhaustion also fail closed.
- Metering flip on the same Settings object while pending; sync/admission interleaving; failed sync
  retains old aliases and discoverable partitions; both stub forms supported.
- Concurrent same request ID assigned to different groups in memory/Table; release required before
  reassignment; ambiguous multiple persisted owners rejected; bounded local identity locks.
- Stream context close exception, cancellation during close/settlement, repeated cancellation and
  cleanup timeout: credit/quota/metrics attempted independently, no leaked tasks or free recovery.
- Run focused tests then full suite including real Azurite transactions (Docker if available),
  coverage >=80%, Ruff, formatting, mypy, Docker build and relative-documentation link validation.
  Update canonical migration/expiry/failure docs, traceability and exact evidence. Run Sonar only
  if its repository script exists. Independent implementation review must assess all five fixes.

## Review gate

Record a different model/session's review of this concrete recovery contract here before code fixes.
Approval must explicitly accept conservative expiry of legacy and pre-egress pending reservations,
and check ETag/intent races and bounded cancellation behavior. This is a semantic accounting change,
not simply an exception-handling patch.

Implementation and fault verification completed: 428 tests, 90.08% coverage, all 11 Azurite tests,
Ruff/format/mypy and Docker build passed. See [recovery evidence](recovery-evidence.md).

### Independent review attempt

Started a separate read-only OpenCode session titled `Independent shared-credit recovery plan review`.
The session failed before review with: `Access denied due to invalid subscription key or wrong API
endpoint`. No independent approval was obtained. Code fixes and verification of the amendment are
blocked on a working reviewer session or operator-provided independent review. Existing 399-test
evidence applies only to the original implementation and does not establish these five fixes.

### Independent approval obtained

Operator supplied approval from separate tool session `ses_ef6422f4effeLjrO87PAowPxJu`.
Approved requirements: full-reserve expiry for legacy/pre-egress rows without valid retained durable
intent; valid intent wins; fresh balance and reservation ETags in the same recovery batch; recompute
on conflicts and no double debit after commit-then-timeout; bounded ownership rejects at its limit
without eviction; failed/incomplete discovery is not absence; protected financial cleanup receives
its own opportunity independent of context close; repeated cancellation is shielded with bounded
join. No additional plan-review session is required. This approval supersedes the blocked attempt.
