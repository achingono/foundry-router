# G1 fence-only recovery operational packet

## Status: Implemented locally; Azure recovery and exact approval pending

This is the executable companion to the [approved recovery plan](activities.md)
and [independent plan review](plan-review.md). It is **not** execution approval.
Only the new [runner](../../../../scripts/quality/table_production_acceptance_recovery.py),
[tests](../../../../tests/unit/test_table_production_acceptance_recovery.py), and
this packet are developer-owned. Original G1 helper `701cca…`, tests `04b79e…`,
original `e` artifacts/ledger, runtime/Docker files and all user work are read-only.
No subagent was delegated; the production developer remains paused.

## Known history and permitted ownership

The original `e` apply consumed its outer identity and original USD 1 / 16-attempt
program, then stopped on `Fence denial unproved`. Coordinator read-only evidence
reports the original old Table image, actual DENY403, same old process, unchanged
two accounts, no old-drained/stop/promotion/restart evidence and zero paid slots
started. These are coordinator observations, not author-executed Azure evidence.
The runner validates the precise known original packet hash, original approval,
outer consumption, failure summary, original immutable ledger/proposal bytes,
absence of all case/operation markers and conflicting journals, and current
read-only configuration/pins/resource/source binding. Marker absence alone is
not its unused-slot proof.

The recovery does **not** create a new ledger, USD 1 allocation, replacement
reservation or fresh four-call budget. It advances only the four original
unstarted slot identities, once, retaining their USD 0.00448 each / USD 0.01792
aggregate reservation, max128 outputs, max64 reported inputs, zero paid retries,
two original single-backend model pools and original configured pricing. Local
estimates and the historical synthetic USD 100 seeds are not Azure wallets.
No production funds, calls, grants, resources or Table seeds are changed.

## Preparation and approval

Caller creates a fresh canonical external directory, owned by the executor,
mode700. Artifacts must be nonsymlink, owned, mode600 and capacity-bounded.
Preparation takes the existing original execution lock nonblocking, reads the
original history and live test/production metadata, resolves pinned Key Vault
values silently in memory and binds only hashes/references. It rechecks the
unchanged production configuration and dedicated test-resource mapping; the
original management-resource disjointness, including endpoint aliases, remains
an exact-review fact to confirm. Frozen runtime/image provenance and new
runner/test hashes are bound in recovery `prepared.json`.

Prepare changes no ingress and makes no inference. It observes DENY403 under a
total120-second deadline. If one old worker exists, it requires the original
process/command, effective environment, original two-account state and request
counters. Zero replicas is allowed **only as deferred financial evidence**, not
proof that Table state is unchanged. The exact approval explicitly authorizes
the controlled min0 warming/rebaseline branch before any stop or paid call.
The current executor IPv4 is newly bound; prefer the original address, but a
changed address requires approval of the new exact packet. The original address
and original ingress remain immutable historical inputs.

```bash
.venv/bin/python scripts/quality/table_production_acceptance_recovery.py prepare \
  --original-dir "$ORIGINAL_E_DIRECTORY" \
  --artifact-dir "$FRESH_RECOVERY_DIRECTORY" --executor-ip "$CURRENT_EXECUTOR_IPV4"
```

The independent reviewer supplies a private mode600 approval JSON with exactly
these keys, using full actual hashes from recovery preparation:

```json
{
  "verdict": "approved",
  "packet_sha256": "new recovery prepared.json SHA-256",
  "original_prepared_sha256": "original e prepared.json SHA-256",
  "original_consumed_sha256": "original e consumed.json SHA-256",
  "original_ledger_sha256": "original immutable program-ledger.json SHA-256",
  "independent_reviewer": "different model/session",
  "recovery_accepted": true,
  "unused_slots_verified": true,
  "staged_fenced_completion_accepted": true,
  "cold_rebase_accepted": true,
  "original_executor_exited": true
}
```

Original executor exit is a coordinator-confirmed gate backed by its completed
failure summary and available execution lock, not an assumption that the
Container App worker stopped. Original approval does not approve this runner.
No actual recovery approval is authored here.

## Single-use apply and exact stage boundaries

```bash
.venv/bin/python scripts/quality/table_production_acceptance_recovery.py apply \
  --artifact-dir "$FRESH_RECOVERY_DIRECTORY" --approval "$INDEPENDENT_RECOVERY_APPROVAL"
```

1. Hold original `execution.lock`, canonical original `recovery-program.lock`
   and recovery-directory `execution.lock` throughout execution. Revalidate
   original hashes, frozen helpers/new executable, current settings and wholly
   unstarted slots. Exclusively create and fsync **original-program**
   `recovery-consumed.json`, then own `consumed.json`, before mutation. Both link
   the new identity/approval to the original packet, consumption, failure and
   immutable program. Another recovery directory cannot bypass this guard.
   Original apply is never called and remains consumed.
2. Prove DENY403. With an existing worker require its exact original identity.
   With no worker, consume one executor-only Allow write, observe public200
   readiness, require sole ready old-image worker and exact original settings,
   command, financial/cycle/legacy-counter state and no new inference request
   counters. Persist `cold-old-baseline.json`, explicitly **not current-image
   persistence acceptance**. Consume DENY and observe403. No further implicit
   rebaseline is allowed.
3. Capture the same baseline process, zero reservations/inflight and unchanged
   accounts/counters; drain100seconds, then recheck. Append new original
   `old-drained.json` and `stop-consumed.json`. Deactivate that old revision once.
   Count all old replicas, including inactive draining revisions, until no
   worker and no active revision exists. Never promote while workers remain.
4. Revalidate the exact original template and existing approved proposal file
   and pins. Append `update-consumed.json`; perform one template-only REST PATCH
   via the original private owner-mode600 `@update-proposal.json` file. Preserve
   all secretRef-only entries, resources, identity, tables, prices, aliases and
   auth; change only the approved current image, retry0 and min1/max1. No CLI
   update, old revision activation, Table reset or grant mutation exists.
   Require sole ready successor, exact configuration/effective hashes, explicit
   current debit/recovery fields initially0, unchanged original account state
   and actual retry0. Missing current fields are never treated as legacy0.
5. Consume executor Allow, observe200/ready, then perform exactly four original
   cases in order. Every `before` must equal the last accepted account map,
   initially the successor baseline. Exclusively append each **original**
   `case-N-consumed.json` before HTTP and a linked ownership record in recovery;
   observe HTTP/terminal numeric usage through frozen bounded dispatch helpers
   before awaiting financial diagnostics. Require200/terminal/clean EOF, valid
   usage and price-matched debit/counter delta within USD0.000002, unchanged
   other groups/cycles/recovery and zero reservations. Persist accepted state
   before another slot. Started or unknown outcomes retain the original full
   reservation and stop all later calls; no retry or recycling.
6. Only after four passes: consume final DENY, observe403, drain100seconds and
   require same current worker and final state/request counters. Consume one
   targeted revision restart. Require changed actual container identity or
   increased restart count, changed process identity on the same approved
   revision, local readiness/effective hashes, full preserved configuration and
   both account/debit/recovery states unchanged. No extra inference is used.

## Real total deadlines and fail-closed recovery

- Overall apply budget:30minutes. Public status/header/body observation:120seconds
  total, including repeated read-only GETs and nested helper timeouts. Known
  startup/propagation200/403/502/503/504 and read timeout observations may poll;
  unexpected auth/status/config or malformed ready data stops. No mutation or
  paid request is retried.
- Writer/readiness/replacement observation:180seconds total, including nested
  CLI calls. Deadline-aware Azure commands use timeouts no larger than remaining
  time. Main-thread SIGALRM bounds synchronous frozen-helper calls; an8-second
  headroom covers its at-most-six-second PTY cleanup before the actual deadline.
  Existing/conflicting process timers are refused, handlers are restored, and
  insufficient remaining time prevents another operation or drain. The frozen
  helper's original per-call timeout is not mistaken for the outer total bound.
  CLI commands run in owned process groups; timeout cleanup kills only that
  group and bounds final collection to at most3seconds and remaining time.
- Every financial/mutation marker is owner-only, exclusive and fsynced before
  its operation. Only previously absent original stage/case/result files are
  appended; original prepared/approval/failure/consumed/ledger/proposal bytes
  are checked repeatedly and never overwritten. No credentials, prompts,
  outputs or raw console/CLI exception text are persisted or printed.
- Any failure keeps actual restrictive ingress (possibly executor-only), tables,
  journal and uncertain consumption. Do not refund, reset, reactivate stale
  images, delete markers, rerun original apply or rerun this recovery. Further
  recovery requires independently reviewed actual current state and a new
  authorized mechanism, not another directory bypass.

## Result chain and remaining gates

Success appends original `results.json` and own `results.json` using schema
`g1-fence-recovery-result-v1`. Required producer fields include
`g1_four_calls_and_restart: passed`, `original_apply_completed: false`, staged
`ingress: fenced` / `min_replicas: 1`, `original_min`, four ordered passed-case
hashes, restart-result hash and `recovery_link`. That link identifies the new
packet/approval/recovery directory and original prepared/consumed/failure/ledger
hashes. Own results additionally bind the original result-file hash. The
original case observation/consumption files remain linked evidence; no old
failed result is relabeled as passed.

A separately reviewed production prerequisite reader must validate this complete
chain and actual four-pass/restart evidence, not merely file presence or the
plan verdict. This accepts isolated G1 on the dedicated resource only; production
account coverage, Table migration and autoscaling are not completed here.

Successful recovery remains **DENY/min1/max1**. Exact original ingress is
`original e prepared.json.original_ingress`, not recovery's DENY baseline;
original min0 is in that same original packet. Cleanup/restoration needs its own
reviewed transition. Ongoing min1 infrastructure cost is not capped by the
runner deadline or original inference reservation. Coordinator must record the
actual fence/outstanding gates and notify the paused writer after lock release.

Local focused verification: **36 passed / 98.18% recovery-runner coverage**;
Ruff check/format and mypy pass. Only mocked prepare/apply paths were exercised;
the author made no actual prepare, Azure, Docker or paid call and no staging,
commit or subdelegation. Hashes are supplied at handoff. Runtime/image are
unchanged; no new Docker/Azurite/Azure pass is claimed. Sonar is absent/N/A, not
a scan pass. Fresh full verifier evidence, independent contextual review, actual
read-only prepare and independent exact recovery approval remain mandatory.
