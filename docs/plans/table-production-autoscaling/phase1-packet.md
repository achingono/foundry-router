# G1 operational harness packet

## Status: Partially implemented — not execution approval

Sole developer: disclosed GPT 6.1 Sol fallback after Muse HTTP 402. Only the new
[harness](../../../scripts/quality/table_production_acceptance.py),
[focused tests](../../../tests/unit/test_table_production_acceptance.py), and this
packet are developer-owned. Existing source, documents, scripts, historical
tables and ledgers remain untouched. Coordinator owns independent review,
read-only prepare, execution evidence, staging and incremental commits.

## Scope and binding

- Phase 0 read-only preparation; Phase 1 existing isolated Table/one image update,
  four sequential Azure Responses cases, and one targeted revision restart.
- Prepare first makes one public `/health/ready` GET to cold-start the existing
  min0 app, with an absolute 60-second deadline and 60-second inactivity bound.
  It then uses a 60-second polling window with individually bounded Azure CLI
  calls to find exactly one ready replica before exec
  diagnostics. This is readiness intake only: no Azure configuration mutation,
  provider inference or HTTP retry. A failed warm/wait leaves no prepared packet,
  reservation ledger or consumption marker.
- No production mutation, infrastructure creation, Table row initialization,
  replenishment, old ledger import, paid retry, failover or autoscaling operation.
- Caller supplies subscription, known app names/resource groups, executor IPv4,
  approved external artifact directory and **new** whole-program ledger path.
  Directory must already exist, be owner-only mode 700; created files are mode
  600, exclusive and fsynced. No historical artifact is overwritten.
- Production immutable image is discovered (or supplied and compared), then
  matched against the caller-provided prior packet's complete runtime Python,
  Dockerfile and dependency-source hashes. Only prior **metadata** is read.
  The new script/test hashes, private current Azure projection, secret versions
  and value hashes, original process, ingress, min replicas, Table coordinates,
  prices, cases and budget are bound in `prepared.json`.
  The template-only PATCH proposal's semantic SHA-256 is also bound there;
  independent review can reconstruct the exact body from the bound original
  template and the pure proposal helper.
- Key Vault references must already include immutable secret versions. Values
  exist only in memory. Inline app secrets are refused. Exec diagnostics read
  admin credentials inside the target child; command arguments contain code,
  never credentials. Neither prompts nor model output nor raw exec/CLI errors
  are persisted. Usage artifacts whitelist only numeric accounting fields.

## Dedicated test liability / S2

Prepare resolves production backend configuration silently, refuses any selected
test host present in that configuration, and binds each test host to exactly one
discovered Cognitive Services management resource endpoint. Apply repeats this
check. An unresolved or overlapping mapping stops before mutation.

Coordinator read-only discovery reports both selected deployments belong to a
dedicated resource outside production's configured inference hosts. This is a
handoff observation, not developer-run Azure evidence; `prepared.json` must
rediscover and bind it. The fresh exclusive USD 1 program is independent test
liability, **not a second allocation of production funds**. The historical
synthetic USD 100 seed stays unchanged and is only a debit-delta baseline, not
an Azure wallet. Neither deployment covers production's active Azure accounts;
G1 demonstrates current-image isolated Table settlement/persistence only.

The independent reviewer must explicitly approve this concrete disjoint-resource
disposition. Shared resources are refused; this harness cannot deduct production
migration allocations or authorize additional liability.

## Exact operations / M1

1. Revalidate bound source/helper, metadata, pinned secrets, model/pricing,
   original process and quiet canonical account state. Refuse conflicting
   replicas/active revisions. Acquire a fresh exclusive lock and create the
   whole-program reservation ledger and irreversible execution marker **before
   mutation**.
2. Apply public deny-all restrictions; require public 403 and the same old
   process through exact revision/replica/container exec. Wait intake deadline
   plus the current client timeout (60 seconds) plus 10 seconds. Require zero
   account reservations/inflight, unchanged balances and request counters.
   Metrics are process-local; no nonexistent forwarding-inflight metric is
   claimed. Readiness is checked locally. Capture the quiet old process.
3. Consume stop operation; deactivate the old revision. Enumerate **all**
   revisions/replicas, counting inactive draining replicas as remaining workers
   only in this deliberate absence-observation path. Poll through that state
   using the bounded 180-second window and individually bounded CLI calls; an
   unexpected active revision is still refused. Prove no worker in any revision
   and no active revision before proceeding. Deadline failure leaves the fence
   and consumption records intact, without update or automatic recovery. Then consume
   image promotion via a **template-only Azure REST PATCH**, not Container Apps
   CLI update; reuse existing configuration/tables/auth, change only the
   current immutable image, `FOUNDRY_RETRY_ATTEMPTS=0`, and min1/max1. Require
   sole ready successor, actual effective environment hashes, unchanged
   financial state and current debit/recovery counters. State-sync errors stop;
   no reset or stale-writer reactivation is available.
   The exact original template is deep-copied; every unrelated environment
   record, secretRef-only entry, resource setting and scale rule is retained.
   The old `revisionSuffix` is omitted so Azure generates the new suffix, as
   permitted by the successor predicate. No secrets, identity, ingress, table
   names or prices are patched. Before consumption, validate the allowed diff
   and persist owner-only `update-proposal.json` plus its semantic/file hashes
   in `update-proposal-binding.json`. After old-worker absence, recheck the
   original template and proposal bytes before the durable update marker, then
   pass the body to `az rest` via `@` private file, never inline configuration
   values in command arguments. Existing successor validation remains intact.
4. Restrict public ingress to the bound executor IPv4 only. Four slots are
   pre-reserved inside the **entire program's** USD 1 / 16 attempt bounds; Phase
   1 consumes at most four attempts, each with max128 output and zero retries.
   Slot reserve is the greater of the current local estimator and a conservative
   64-input/128-output price ceiling. Every slot has an exclusive durable marker
   before HTTP. Unknown results retain the whole reservation; no slot recycling.
5. Require public HTTP 200, clean terminal completion/usage and bounded SSE EOF.
   Persist header status and numeric observation before subsequent diagnostics;
   terminal SSE observation is persisted before awaiting more frames. Compare
   current configured cached-input pricing, one canonical account balance/debit
   delta (tolerance USD 0.000002), unchanged other groups/cycles/recovery counters
   and zero reservations. Any failure stops all remaining calls, without retry.
   Before consuming each slot, require financial equality with the last accepted
   canonical account map, initially the successor baseline. Replenishment,
   unexpected debit/recovery, other-group changes, membership drift and cycle
   changes between cases all stop before the next slot or HTTP dispatch. Every
   public diagnostic GET also has a total 60-second deadline covering headers
   and body, not merely an inactivity timeout; trickling bytes cannot extend it.
6. Only after all four pass: deny public intake again, prove 403, wait drainage,
   require unchanged final accounts/counters and same sole process, durably
   consume restart, and restart that revision once. Poll bounded read-only
   replica metadata for a changed actual container identity or increased restart
   count; require changed process identity, ready local diagnostics, exact
   effective settings, and unchanged persisted account state. Transport failure
   is not acceptance and triggers no restart retry.

## Restoration and recovery disposition (review required)

Successful G1 deliberately ends **fenced at min1/max1**. Exact restoration inputs
are `prepared.json.original_ingress` and `prepared.json.original_min`;
`results.json` records only the staged outcome and original minimum, not the
original ingress policy.
Restoring min0 creates another revision; that transition is **not included in
this executable**, must not be represented as completed, and needs a separate
fresh reviewed restoration packet after G1 results. The reviewer/coordinator
must explicitly accept this staged completion before apply, or require a reviewed
restoration extension before binding the actual packet.

On failure retain the current restrictive ingress, all original tables and
consumed records. Inspect current state read-only. Do not replay the program,
reset balances, refund uncertain debits, reactivate the old image, or use a stale
seed as rollback. Ambiguous stop/update/restart requires a new reviewed recovery
packet based on actual current state. No automatic recovery mutation exists.

## CLI and independent approval

```bash
.venv/bin/python scripts/quality/table_production_acceptance.py prepare \
  --subscription "$SUBSCRIPTION" \
  --production-rg "$PRODUCTION_RG" --production-app "$PRODUCTION_APP" \
  --test-rg "$TEST_RG" --test-app "$TEST_APP" \
  --models "$MODEL_ONE" "$MODEL_TWO" --executor-ip "$EXECUTOR_IPV4" \
  --prior-metadata "$PRIOR_PREPARED_METADATA" \
  --artifact-dir "$APPROVED_PRIVATE_DIRECTORY" \
  --program-ledger "$FRESH_PROGRAM_LEDGER"
```

After prepare, a fresh independent reviewer examines the actual executable,
hashes, mocks, resources, configuration/state, dedicated liability, budget and
staged restoration, then supplies a private approval JSON containing:

```json
{
  "packet_sha256": "actual prepared.json SHA-256",
  "verdict": "approved",
  "independent_reviewer": "different reviewer/session",
  "m1_closed": true,
  "liability_reserved_outside_production": true,
  "staged_fenced_completion_accepted": true,
  "liability_disposition": "actual disjoint resources and fresh exclusive program"
}
```

Only the coordinator may subsequently execute:

```bash
.venv/bin/python scripts/quality/table_production_acceptance.py apply \
  --artifact-dir "$APPROVED_PRIVATE_DIRECTORY" --approval "$INDEPENDENT_APPROVAL"
```

This document and plan approval are not substitutes for exact prepared approval.
The author does not approve or execute their own packet.

## Verification inputs and remaining gates

Coordinator reports current baseline 2,887 passed / 90.46% coverage, Ruff/mypy
passing; 15 fresh real Azurite tests passed; the exact production digest was
pulled and network-disabled Azure Table/client/credit/quota/aiohttp/main imports
passed. Attach coordinator's actual artifacts to independent review; these are
not developer reruns or Azure G1 passes. Sonar script is absent (N/A, not passed).

The original implementation verification was 56 passed / 95.19% harness coverage.
Post-review focused verification: **83 passed / 96.93% harness coverage**;
focused Ruff check/format and mypy pass. The previous review hashes cannot
approve the corrected executable. No Azure, Docker, paid HTTP, staging or
commits were executed by the developer. Independent contextual
deep/exact review, actual read-only prepare, Azure fence/deactivation/update,
four fresh calls, targeted restart, and original ingress/min0 restoration remain
unverified. Production remains memory/one; Phases 2–6 remain outside this change.

### Remediation and fresh prepare disposition

IR-M1 adds chained financial continuity before every slot; IR-M2 gives public
diagnostics an absolute async deadline. IR-S1 corrects the restoration artifact
pointer; IR-S3 adds stalled/fragmented terminal and unchanged restart rejection
tests. Native exceptions report only exception type and withheld details;
`RefusalError` reports its developer-authored literal operational reason, never
raw Pydantic, HTTP or Azure command output.

Coordinator's first read-only prepare attempt stopped before writing any
prepared packet, ledger, mutation marker or paid-call record. Coordinator
investigation reports matching source/settings/modes, two selected models,
dedicated resource mapping and USD 0.01792 reserved estimate, but the isolated
min0 app had no replica and a 10-second readiness request timed out cold. These
are coordinator observations, not developer Azure execution. The corrected
prepare warms readiness before targeting exec. Use a fresh approved directory
for the next prepare (coordinator's planned `b` directory); do not clear/replay
historical artifacts. No exact prepared approval exists yet. After fresh
verification and prepare, require another independent exact review against the
corrected script/test/packet hashes. Concrete management resource identities
must be checked for disjointness in that review, including endpoint aliases.

### Exec transport shortening (fresh binding required)

Coordinator reports the subsequent read-only prepare in the fresh `b` directory
also stopped before any prepared packet, ledger, mutation or inference. The full
plaintext snapshot program's base64 exec command received WebSocket 404, while a
short diagnostic succeeded against the same exact revision/replica/container.
Coordinator then successfully captured the unchanged full program's ready
two-account snapshot using zlib compression plus base64. This suggests command
length as a transport factor; it does **not** establish an Azure query-length
limit or prove the exact cause of the 404.

The harness now compresses the original `SNAPSHOT_PROGRAM` bytes directly with
zlib level 9, base64-encodes only those compressed bytes, and decompresses them
in the child before exec. There is no outer/double base64 wrapper, change to the
plaintext program semantics, or credential in the command. The focused test
verifies exact byte round-trip, command shape, absence of plaintext admin keys
and a local regression length bound of 1,800 characters (not a platform limit).
No exec retry or console logging was added.

Coordinator reports source-freeze full verification of 2,970 passed / 21 skipped /
90.46% coverage and clear corrected implementation review before this minimal
transport change. Those remain coordinator observations, not developer reruns.
The new transport hashes need fresh verification, the planned fresh `c` prepare
and binding, then independent exact review before any apply; previous attempts and
historical artifacts remain untouched. No prepared approval or G1 pass exists.

### EP-M1 absence-transition remediation (fresh packet required)

The exact review of coordinator's unconsumed `c` packet identified expected
inactive-but-draining replica metadata being rejected immediately. The harness
now permits that state **only** via `writers(allow_draining=True)` in the
deliberate absence wait. All revisions and replicas remain counted, including
multiple inactive draining revisions; zero workers and zero active revisions
are prerequisites to image promotion. Active revisions during absence wait,
steady-state inactive workers, readiness conflicts and replacement conflicts
remain refused. No deactivation retry, old-revision reactivation or rollback
was added. Tests cover active/one → inactive/draining → inactive/empty, all-revision
enumeration, no promotion on persistent drainage/deadline, unexpected active
revision rejection and unchanged strict readiness/replacement guards.

Changing helper/test hashes invalidates the unconsumed `c` binding. Preserve it
unchanged and use coordinator's planned fresh `d` preparation after verification,
then independent exact review. The frozen 76 runtime Python files, immutable
image, financial chain, paid-call bounds and staged fenced/min1 disposition are
unchanged. No new prepared approval or execution evidence is claimed here.

EP-M1 focused verification: **87 passed / 96.95% harness coverage**; focused
Ruff check/format and mypy pass. This is local mocked evidence, not an Azure
deactivation observation or full source-suite rerun. Developer made no Azure,
prepare/apply, provider calls, staging, commits or runtime/Docker changes.

### EP-M2 CLI normalization avoidance (fresh packet required)

Coordinator's installed Azure CLI 2.91.0 source inspection found that Container
Apps CLI update adds `value: ""` to environment entries without `value`, including
secretRef-only entries. Historical Table metadata evidence records the same
normalization causing a binding failure. This is source-observed evidence, not
a developer-run Azure mutation. The old image/retry/min CLI update path would
therefore predictably violate the exact successor predicate after stopping the
old worker.

Only that mutation is replaced with a narrow REST PATCH of `properties.template`
from the exact bound/current original template. The pure helper validates the
existing allowed-difference predicate before any consumption, preserves all
secretRef-only entries without introducing `value`, and does not mutate its
input. The private proposal and hashes are persisted before mutation consumption;
the request uses the bound app ID and an owner-mode-600 body file. No CLI update
is invoked. Tests cover preservation, original-input isolation, resource/rule
and secret-reference drift refusal, PATCH scope, pre-consumption binding failure
and REST-only orchestration. No cleanup/restoration feature was added.

Coordinator reports 2,974 full tests / 90.46% source coverage for the previous
frozen hashes. EP-M2 changes helper/test hashes, invalidating the unconsumed `d`
packet; preserve it and require a fresh preparation and independent exact review
after verification. All 76 runtime Python files, Docker/source/image pins and
user work remain unchanged. No mutation, inference or execution approval is
claimed by this remediation.

EP-M2 focused verification: **95 passed / 97.10% harness coverage**; focused
Ruff check/format and mypy pass. This verifies local mocked proposal/orchestration
behavior only; the REST promotion remains an independently approved live gate.
