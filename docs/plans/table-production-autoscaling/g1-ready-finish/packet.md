# Ready-only G1 finish capsule

## Status: Implemented locally; contextual review passed; exact execution approval pending

This capsule implements the [approved plan](activities.md) and
[independent plan review](plan-review.md). Only the new
[runner](../../../../scripts/quality/table_production_acceptance_finish.py),
[focused tests](../../../../tests/unit/test_table_production_acceptance_finish.py),
this packet, and the [independent implementation review](implementation-review.md)
are task-owned. Original G1, recovery and continuation source/tests and all e/a/D
artifacts are read-only. No prior apply/history entrypoint is invoked. No
deployment/image PATCH, old stop, old warming/activation, role/resource/table/seed,
pool/price, or production mutation path exists.

Current revalidation included read-only Azure resource/revision/replica queries
and public readiness GETs. It did **not** run fresh capsule preparation, ingress
mutation, provider inference, restart, deployment, or production migration.
Historical ready evidence and these read-only observations do not replace
execution-time guards.

## Starting state and scope

Coordinator reports API2025 promotion succeeded, followed by the D checker's
transient `Inactive revision has workers` refusal before any case or successor
baseline artifact. The supplied ready capture has one approved active ready
current-image Table/min1/max1/retry0 worker; three old inactive revisions have
zero workers. Both current account maps equal original old-drained; current
debit/recovery fields are explicitly present0 and public status403. Its full
SHA-256 is pinned; this is historical capture evidence, **not a replacement for
live checks** and not proof of G1 inference/persistence acceptance.

The executable can perform only executor Allow, four original unused cases,
final DENY/drain and one restart. There is no deployment/image PATCH, old stop,
old warming/activation, role/resource/table/seed, pool/price or production
mutation path. Original program USD1/16 attempts and original four slot
identities/USD0.01792 reservation remain unchanged; no new ledger/allocation or
refund is created. All balances/prices remain local estimates, not Azure wallets.

## Read-only prepare

Caller supplies canonical owned mode700 directories and mode600 nonsymlink
artifacts. Coordinator must harden D's existing summary permissions to600
without changing its bytes before preparation. The author does not alter that
summary or any private evidence.

```bash
.venv/bin/python scripts/quality/table_production_acceptance_finish.py prepare \
  --original-dir "$ORIGINAL_E" --recovery-dir "$RECOVERY_A" \
  --continuation-dir "$CONTINUATION_D" --ready-evidence-dir "$READY_EVIDENCE_DIRECTORY" \
  --artifact-dir "$FRESH_FINISH_DIRECTORY" --executor-ip "$CURRENT_EXECUTOR_IPV4"
```

Prepare holds original execution/program/continuation and prior executor locks.
It binds complete e→a→D consumed/failure/promotion hash manifests, original
budget and four wholly unstarted slots, the exact ready capture, immutable
helper/test/runtime/image hashes and new finish/test hashes. Original
successor-baseline/case/restart/results files must be absent; any case HTTP,
terminal, observation, ownership or conflicting journal rejects the prefix.

Live discovery explicitly lists all revisions with `--all`, then each replica
set. Require one approved active ready worker on the captured current revision;
every other revision is inactive with zero workers. Compare raw current
configuration against the ready projection and the original permitted
image/retry0/min1 diff. The original projected literals are hydrated only from
hash-verified current literal values or recorded original retry; projected hashes
are never reused as raw values or double-hashed. SecretRef-only entries, resources,
prices/allowances/seeds, tables, identity and non-`FOUNDRY_` controls stay bound.
Resolve pins silently, verify actual environment/command/readiness, and require
both current account/cycle/debit/recovery maps exactly old-drained with explicit
current counters and zero reservations. Fresh production metadata/pins and
dedicated test mapping are read-only drift checks; production funds/calls are out
of scope. Require live403 and the exact supplied/current process and generation.

`prepared.json` records current projection, baseline, all-revision inventory,
source/history/evidence hashes, original slot objects and newly bound executor
IPv4. Neither a warm replacement nor zero-worker baseline is allowed here.

## Independent approval

A separate reviewer verifies the actual private packet, source/tests, live
settled state, ownership and original-unused-slot proof. Inspect the complete
approved current revision template in `prepared.json`—including revision-only
probe values—and confirm the app/revision comparison removes only the observed
null/missing `revisionSuffix`, revision-only `probes`, app-only
`ephemeralStorage`, and revision-null cooldown/polling fields. Any other template
difference or unsuitable probe configuration refuses approval. The reviewer
then supplies exactly:

```json
{
  "verdict": "approved",
  "packet_sha256": "actual finish prepared SHA-256",
  "independent_reviewer": "different model/session",
  "prior_hashes_sha256": "semantic hash of complete prepared.prior_hashes",
  "ready_sha256": "actual pinned ready.json SHA-256",
  "revision": "actual approved current revision",
  "generation_sha256": "semantic hash of prepared.baseline.generation",
  "finish_accepted": true,
  "unused_slots_verified": true,
  "current_ready_old_workers_zero": true,
  "financial_equality_verified": true,
  "previous_executors_exited": true,
  "production_writer_paused": true,
  "staged_fenced_min1_accepted": true
}
```

This document and earlier approvals are not executable finish approval. The
author creates no actual approval. Prior executors' exit and paused ownership
are coordinator-confirmed gates backed by nonblocking locks and immutable
failed histories, not assumptions that old app workers stopped.

## Once-only finish

```bash
.venv/bin/python scripts/quality/table_production_acceptance_finish.py apply \
  --artifact-dir "$FRESH_FINISH_DIRECTORY" --approval "$INDEPENDENT_FINISH_APPROVAL"
```

1. Hold original execution/program/continuation, recovery execution,
   continuation execution, new original `ready-finish.lock` and new execution
   locks throughout. Revalidate complete source/history, actual ready topology,
   exact process/environment/finances and live403. Exclusively fsync original
   `ready-finish-consumed.json` plus new own consumption before mutation. Another
   directory cannot bypass this guard; earlier consumed guards remain intact.
2. Append original `successor-baseline.json` only if absent. Consume one
   executor Allow write and observe200/ready under the frozen120-second total
   deadline. There is no deployment, second stop or initialization operation.
3. Before every original case require the same strict sole current worker,
   unchanged configuration/pins and complete `before==last_accepted` map.
   Exclusively append original `case-N-consumed.json` before HTTP plus linked
   finish ownership. Use frozen minimal bodies/dispatch: one attempt per original
   slot, max64 input/max128 output, zero retries/failover/substitution. Numeric
   HTTP/terminal observations precede financial awaits; require200/completed/
   clean EOF and configured cached-usage pricing. Debit must fit the original
   reserve and balance/debit counter toleranceUSD0.000002; other groups/cycles/
   recovery are unchanged and reservations0. Advance only after acceptance.
4. Only after all four pass: consume DENY, prove403, drain100seconds and require
   the same process/request counters and final financial map. Consume one
   restart of the approved current revision.

## Restart observation is not acceptance

Only after the final proved fence and quietness, bounded observation may see
0workers, an inactive current candidate or2current workers. Every such worker
must belong to the same approved current revision/image/exact template; any
old-version or unapproved revision worker or activity refuses immediately.
Multiplicity above2 is refused. Metadata for all revisions is always read;
the original frozen sole-worker guard is not used to abort this narrowly
authorized rolling interval.

The observation loop can accept only one active current revision/one **ready**
current worker with a changed actual container ID/replica identity or increased
restart count. Final local snapshot must also show changed actual process,
same approved command/effective environment/configuration, ready state and both
persisted balances/debit/recovery counters exactly equal to the four-case final
map with reservations0. Recheck live403 before recording persistence/results.
A no-op, timeout, old worker, financial change or transport failure is not a pass.
No post-restart inference is authorized.

Overall30minutes, public propagation120seconds and restart observation180seconds
are genuine remaining-budget bounds using frozen recovery wrappers, individually
confined CLI/HTTP calls and subprocess cleanup headroom. Read-only observation
GETs are not paid retries. Every mutation/case has a durable exclusive marker;
errors preserve actual restrictive policy and liability without automatic
mutation retry, old-image activation, slot reset, refill, refund or recovery.
Native CLI/HTTP details are withheld; no credentials, prompts, outputs or raw
console are persisted. Local estimates are never presented as invoice balances.

## Result chain and outstanding work

Append only new original baseline/case/restart/results and own journals/results;
never overwrite e/a/D prepared, approval, consumed, promotion or failure bytes.
Original result schema remains `g1-fence-recovery-result-v1`, with actual four
case receipt hashes (each linking HTTP, response/usage, and stream EOF evidence
where applicable) and restart hash, `original_apply_completed:false`, inherited
`recovery_link`/`continuation_link`, new `finish_link`, complete prior manifests,
new dependency/source binding and ready-evidence hash. Own results additionally
hash the original result file. Production's reader/final reviewer must validate
this complete actual chain, not merely file presence or an earlier plan verdict.

Success remains **isolated test DENY/min1/max1**. Exact original ingress/min0
cleanup is a separate reviewed task; original restoration inputs remain in e's
original prepared packet, not the current ready DENY projection. Ongoing min1
infrastructure spend is not capped by the inference reservation or runner
deadline. This does not migrate production or qualify autoscaling/provider
admission/embeddings. P2 drafts and all production/user work remain untouched.

Latest local verification after review fixes: focused finish tests **48 passed /
98.58% finish-runner coverage**; full repository suite **3,134 passed, 21
skipped, 90.46% runtime coverage**; full Ruff check/format, source Mypy, and
operator Mypy with `MYPYPATH=src:scripts/quality` and
`--explicit-package-bases` passed. The independent contextual review found no
Critical or Major findings. These are local/mocked results, not live acceptance.
The repository has no SonarQube script (N/A, not a scan pass). Frozen helper and
full 76-runtime-file/image hashes justify scoped prior Docker/Azurite reuse, not
new pass claims. Fresh private prepare, actual exact executable approval,
isolated live inference/restart, and separate restoration review remain pending.
