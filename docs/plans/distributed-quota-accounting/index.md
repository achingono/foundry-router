# Distributed quota accounting

**Planned**, 2026-10-08. Workstream 5a of the
[routing roadmap](../google-ai-routing-order/index.md). Production remains memory/one.

## Contract

Introduce an opt-in `rate_limit_backend: table` independent of credit `state_backend`.
Require explicit identity-only Table endpoint and quota table name, with no infrastructure
provisioning in this code phase. Existing memory/share behavior remains the default.
Table mode enforces full configured project/quota-group limits across workers and replicas;
replica shares do not divide shared limits. Quota remains separate from monetary credit.

Use the existing injected Table client and ETag conditional transactions. Extend its explicit
recoverable-conflict allow-list to the quota state row while retaining mandatory ETags for
that row; do not convert arbitrary 409/412 errors into harmless contention. A quota group owns
one state row, so admission, minute usage, Pacific-day counts and pending reservations change
atomically. Store bounded JSON in one property (maximum 48 KiB measured as UTF-16-LE bytes of the serialized Edm.String,
maximum 256 retained records
per group); reject admission at record/byte capacity rather than evicting pending ownership.
This intentionally trades throughput for correctness for the configured free-tier workload.
No new storage service, distributed lock or cross-partition identity index is required.
Hash configured quota-group IDs for safe bounded partition keys, keeping logical group labels
in validated state; bound server-owned quota attempt IDs to 128 UTF-8 bytes. Table mode requires
nonempty configured limits for every admitted group and a finite reservation max age of at most 3,600 seconds (default remains 900).

A record retains a server-owned **quota attempt ID**, UTC admission timestamp, estimated input tokens and
pending/finalized state. Quota attempt IDs are unique across writers. The logical request ID
continues to own credit/telemetry; each candidate quota admission gets a distinct attempt ID,
created once and carried in BackendSelectionResult through execution, streaming callbacks,
finalization, cancellation, explicit release and failover. Finalize the first attempt before
reserving a fresh second attempt, including within the same group: both dispatched attempts
consume RPM/RPD, and first usage is never erased by reusing the logical request ID.
Only retry the same atomic storage operation with the same attempt ID. Daily count is aggregate by
Pacific date; minute records remain through a conservative 70-second window. Pending records
remain until settlement or the bounded reservation age; age-based cleanup finalizes the
estimate and **never refunds** the daily request count. Explicit release is only for confirmed
non-dispatch: remove minute estimate and decrement the matching admission day's daily count.
Finalization replaces estimate with known input usage, or preserves estimate when unknown.
Idempotent duplicate finalization/release does not double-change counters. Re-admission of an
already recorded ID is forbidden until confirmed retirement; ambiguous ownership is not
capacity rejection.

Clock assumption: participating hosts are UTC-synchronized within five seconds. A 70-second
retention window covers pairwise skew for a true 60-second quota. Block new admissions when
`now - 5 seconds` and `now + 5 seconds` fall on different Pacific dates; do not assign those
ambiguous requests to yesterday and then discard them at reset. Outside this ten-second
uncertainty interval, use the common Pacific date. Persist current and previous day counters
while pending records need explicit-release bookkeeping; expiry never decrements either.
Clock regression relative to persisted watermark fails closed. Test UTC/Pacific boundaries,
DST and clock regression. This assumption and conservative window are explicit rollout gates;
local wall-clock verification does not establish deployment clock guarantees.

Persist a settings fingerprint with the row covering numeric limits, schema/version,
70-second accounting window, five-second skew guard, reservation expiry age and quota-group
membership/retirement policy. Shorter-age writers cannot silently expire another writer's
longer reservation. New row initialization is create-if-absent;
restart never zeros shared usage. A different active limits fingerprint fails closed until
all writers are drained, expired pending records are conservatively finalized, no pending
records remain, the 70-second usage window is empty and the prior stored admission day has
fully elapsed outside the clock-uncertainty interval. These are the concrete CAS transition
predicates; retaining yesterday's count cannot create today's allowance. Configuration writes
use fresh ETags, and callers verify persisted fingerprint on every admission. There is no live
mixed-config merge or destructive admin reset. Table `reset()` clears local bookkeeping only. Store
exceptions/conflict exhaustion are typed failures, not `False`; routing must retain possible
ownership and avoid alternate dispatch. The existing protected emergency `allow_over_limit` policy may explicitly exceed configured
quota limits, but never row capacity or storage correctness gates; document and test this
exception so configured caps are only guaranteed for ordinary admissions.
Successful compare-and-swap followed by lost
acknowledgement must remain recoverable by reading the same record. Retries are bounded
(eight conflicts); diagnostics contain group/error categories, never request content/secrets.

Existing routing admission/finalization and cancellation paths use the same store protocol.
Add explicit QuotaStoreError handling to initial and failover selection: return sanitized
503 `quota_store_unavailable`, never dispatch another backend on uncertain admission.
Cleanup failures must not mask the typed admission error or escape as public tracebacks;
retain uncertain records for conservative expiry. Do not reuse monetary CreditStoreError. Startup, readiness, admin and routing compare the same full-vs-shared effective-limit
contract. Table readiness probes the quota client as well as any credit/health clients.
Finalize/release discover persisted quota attempt IDs across the finite configured groups when local
ownership is absent, allowing another writer or restart to settle. Discovery failure is not
absence, and duplicate ownership raises a typed ambiguity. Group membership changes require
a drained rollout; no implicit migration or eviction.

## Verification and deployment boundary

Independent plan review must clear Critical/Major findings before runtime edits. Unit tests
use an atomic fake client with simultaneous independent stores, conflicts, commit-then-timeout,
restarts, bounds, clock/day transitions, full counters, shared aliases and unknown settlement.
Actual Azurite tests use independent clients/stores and verify concurrent caps, persistence
and near-boundary UTF-16 property sizes with Unicode attempt IDs. Serialize deterministically
and validate the exact encoded string before every write; 48 KiB leaves margin below the
64 KiB Edm.String limit. Capacity rejection must leave persisted counters unchanged.
API tests prove no dispatch on storage failures, cleanup and operation grouping; 429
failover within the same quota group retains both distinct attempts, and lost-acknowledgement
finalization cannot settle a newer attempt by logical-ID reuse. Run unchanged
memory tests, full ≥80% coverage, Ruff/mypy, Docker, contextual review, documentation links and
final diff. No real provider admission or Azure multi-replica support is claimed here.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
