# Persistent per-combination failure exclusion

**Implemented**, synthetic verification; first independent review returned NOT CLEARED with binding
conditions (all folded in), a second verification round confirmed C1/C3 but held C2
open on the predicate, and the C2 hook-placement fix plus a deep review of the
implementation below are now folded in as well — a short third-round check of the C2
fix and the deep-review findings (probe-clear/re-arm, wall-expiry value, exhaustion
reporting, cutover gate) and admission-ticket concurrency fixes cleared final independent
review with no Critical/Major findings. Production deployment remains separate. Serves track
priority 4 (routing excludes inaccessible combinations). Live evidence: 2.5 models 404
on projects 3–5 while 3.x succeeds there; 3.8-flash streaming stalls/fails on projects
2–5 while its nonstreaming works everywhere.

## Key and scope

- Key is `(backend_id, operation, stream_mode)` where `stream_mode` is derived
  deterministically at selection time as `bool(body.get("stream"))` and the same
  derivation is used for counting. Streaming and nonstreaming both travel as
  `operation="responses"`, so an `(backend, operation)` key would exclude working
  nonstreaming traffic after streaming failures — backend-wide exclusion is rejected
  for the 2.5-model evidence and operation-wide exclusion is rejected for the
  streaming evidence for the same reason.
- Backend granularity is physical: one `backend_id` serves one configured deployment,
  so excluding a backend removes it from every logical model pool sharing it. Admin
  and telemetry list affected logical models per excluded triple (derived from
  `settings.models` pools containing the backend).
- Exclusion is per combination, never per model: an unknown future model on a healthy
  backend is unaffected.

## Counting predicate (exact)

Count a finished attempt iff all hold, evaluated on the **translated
downstream-facing** result fields (`BackendRequestResult.response.status_code`,
`retryable_failure`, `confirmed_pre_dispatch`) **at exactly one hook placement**:
the terminal-attempt-result handling inside `execute_with_single_failover`'s
attempt loop. Streaming paths that hand a `StreamingResponse`/`DeadlineStreamingResponse`
to the caller never produce a countable terminal there — prefetch/prefirst-byte
terminal results count; post-first-byte in-stream stalls surface as in-stream error
events downstream of the hook and never touch the counter. `BackendRequestResult`
carries no first-byte signal and none is added; placement, not a new field, is the
discriminator (`force_charge` is not one either — it also marks prefetch failures):

- `not result.confirmed_pre_dispatch` (nothing counted that was never sent), and
- `500 <= status_code <= 599` (provider 5xx and synthesized transport/timeout 502s),
  or `status_code == 404` (model-not-found class = persistent inaccessibility).

Dispositions, all explicit:

- Router-synthesized 404s (unknown logical model) never produce attempt results, so
  they cannot enter the table.
- Caller-caused 404 is not a meaningful class here: upstream uses the configured
  `deployment`, never caller input.
- Azure 404 during deployment propagation is transient but counts; three consecutive
  occurrences plus probe recovery (below) bound the harm.
- `429` never counts (quota path owns it); other 4xx never count.
- Successes decrement (below); `confirmed_pre_dispatch` failures never count.
- Azure/Google asymmetry is intended as specified: Google pre-dispatch failures set
  the flag and are skipped; Azure terminal `TransportError` leaves it unset and
  counts. A local fault (DNS/proxy/egress) therefore counts per combination and can
  exclude all combinations after 3 each under `maxReplicas: 1`; recovery follows the
  same probe/decay path, and the per-combination bound (next section) limits the
  blast radius. No `force_charge` input to the predicate.

## Counter, threshold, expiry, probe

- Counter `c` per triple, starting 0: qualifying failure → `c += 1`; success →
  `c = max(0, c - 1)` (decay, not clear — a chronic ~67% failure pattern still
  accumulates to threshold instead of flapping forever). No record is materialized
  for non-events (uncounted failures, successes at zero).
- Entry at `c >= 3`: excluded until `monotonic() + 30 min`, with a wall-clock
  expiry (`entry wall + window`, never the entry moment) for display.
- While excluded the triple normally receives no traffic. The only observations
  possible in that state are probes, handled statefully: success on an excluded
  triple clears the window and resets `c = 0` at once (a probe success proves
  health; decay alone would leave a recovered triple excluded up to 30 minutes);
  countable failure on an excluded triple refreshes a fresh 30-minute window
  without emitting a second entry metric.
- On expiry: clear the exclusion and reset `c = 0` (a 30 failure-free-minute epoch
  is a health epoch; re-exclusion of a still-sick triple costs at most 3 fresh
  user-visible failures plus 1 probe, the documented flap bound).
- Last-resort probe (not a retry loop): when exclusion would empty the candidate
  set, retain excluded alternatives through credit/quota admission, then atomically
  claim the oldest admissible triple once, marked in telemetry as
  `combination_excluded_probe`. Success clears counter and exclusion; failure
  re-arms a fresh 30-minute window. There is no background retry of excluded
  combinations — the probe is a foreground, single, telemetry-marked attempt only.

## Admission ownership amendment

Each selected attempt carries an immutable admission ticket with the combination,
store epoch, exclusion generation, and optional probe token. Claim happens after
credit/quota admission; a rejected claim refunds only those pre-dispatch reservations.
Only one probe is in flight per triple. Candidate alternatives remain available when
the oldest excluded backend cannot obtain credit or quota. Every expiry/reset advances
the generation/epoch, and stale completions cannot mutate the newer exclusion state.
Expiry normalization is shared by recording, filtering, and diagnostic snapshots.
Matching probe completion clears/re-arms; uncounted outcomes, cancellation and
pre-dispatch admission failure release the claim without changing the window. Ordinary
attempts admitted before exclusion cannot subsequently clear it. These constraints
replace the earlier assumption that all completions arriving during exclusion are probes.

## Selection and failover integration

- Both selection legs (`select_candidate_backend` first and failover
  `second_selection`) consult the table with the same derivation.
- Failover `excluded`-backend-set and table exclusion compose by union.
- Reason precedence in telemetry: `DISABLED > combination_excluded >
  combination_excluded_probe > cooldown`, logging both reasons where both apply.
  Exhaustion reporting follows the probe: because the last-resort probe keeps a
  fully excluded set routable, selection never fails *due to* exclusion, and the
  `combination_excluded_probe` decision reason is itself the exhaustion signal.
  The pre-filter empty path (`not quota_eligible`) cannot carry exclusion markers
  (the filter never runs on an empty set); downstream health/cooldown failure
  responses continue to report health truth rather than exclusion state.
- A quota- and health-eligible all-excluded set reports the distinct
  `combination_excluded_probe` decision reason; it is not a separate terminal error.
- Existing per-attempt cooldown is untouched (transient layer); operator `DISABLED`
  keeps precedence over everything.

## Visibility, clocks, concurrency, restart

- `admin/status` lists excluded triples with current counts, wall-clock
  (`time.time()`) expiry timestamps, and affected logical models. Expiry checks use
  `time.monotonic()`; the two clocks must never be mixed in implementation.
- Metrics: `combination_exclusion_entries_total` and
  `combination_exclusion_resets_total` labeled `(backend_id, operation,
  stream_mode)`; label cardinality is bounded by configured backends × operations ×
  stream modes. Worst-case flap cost per sick triple per epoch is 3 fresh failures
  plus 1 probe when the set empties (not 3).
- The store takes a lock like `InMemoryHealthStore._lock`; concurrent requests
  share it, with a concurrent-failures counting test.
- Memory-backed limitation (explicit bound, not hand-waved): counters reset on
  restart, costing at most 3 user-visible failures per sick triple before
  re-exclusion. With ~10 triples (5 projects × 2 modes) the worst case is small and
  re-learning staggers naturally with traffic, so jittered re-entry is rejected with
  this reason recorded. Lifespan logs a `combination_exclusion_reset` line at startup
  (no secrets). The store is a module-global singleton wired raw rather than through
  the table-backend `_LiveStore` machinery, as an explicit production-cutover gate
  next to the `maxReplicas: 1` constraint: with >1 replica each replica would learn
  exclusions independently. Table-backed persistence across restarts is out of scope.

## Required tests and verification

- Unit: counting predicate truth table (5xx/transport/timeout/404 in;
  429/4xx/pre-dispatch/success out; translated-status basis); stream vs nonstream
  key separation in both directions; threshold entry at exactly 3; decay (fail/fail/
  success/fail/fail/fail enters; chronic flap accumulates); fixed-window expiry with
  reset-to-0; last-resort probe marks telemetry, clears on success, re-arms on
  failure; empty-set reporting distinct from cooldown; concurrent counting under a
  shared lock.
- Streaming boundary: prefetch/prefirst-byte terminal failures count; post-first-byte
  in-stream stalls never touch the counter (no-retry-after-meaningful-output rule);
  tests for both.
- Integration: mixed pool where one triple fails persistently while the same
  backend's other mode serves (proves the C1 key); failover leg skips an excluded
  triple for the healthy one; single-candidate-excluded still probes; recovery
  passage after success; cooldown behavior unchanged underneath.
- Full suite ≥ 80%, Ruff/format/mypy/Docker, deep review, docs and link/secret
  review. No cap, pricing, or production-topology changes.

## Explicitly out of scope

Cross-restart persistence, per-model (as opposed to per-backend) keys, 429-driven
exclusion, background retry of excluded combinations, post-first-byte stall
exclusion (needs a separate stream-settlement-feedback design), and any change to
credit/quota accounting.
