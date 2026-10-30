# G1 API2025 continuation capsule

## Status: Implemented locally; exact execution approval pending

Companion to the [approved plan](activities.md) and [independent review](plan-review.md).
Only the new [capsule](../../../../scripts/quality/table_production_acceptance_continue.py),
[tests](../../../../tests/unit/test_table_production_acceptance_continue.py) and this
packet are developer-owned. Original G1 `701cca…`/`04b79e…`, recovery
`e3c47…`/`762df8…`, all `e`/`a` artifacts, runtime/Docker and user work remain unchanged.
Neither frozen apply/history entrypoint is invoked. No delegation, Azure,
actual prepare, Docker, paid calls, staging or commits were performed by the author.

## Stopped prefix, not replay

Coordinator reports recovery `a` completed controlled old-image warming,
DENY403 and stable100-second drainage, then deactivated the old revision and
proved all old workers/active revisions absent. The consumed API2024-03-01
template PATCH returned a correlated schema400 for unsupported
`ContainerAppScale.cooldownPeriod` / `pollingInterval`; current metadata still
shows the old image, unchanged template/Table/min0 and DENY with no workers.
Zero original paid slots started. These are coordinator observations, not author
Azure evidence, and are revalidated/bound before execution.

This capsule authorizes **one distinct API2025-01-01 PATCH** with the same
original owner-mode600 `update-proposal.json` bytes, not replay of either failed
executor or consumed2024 operation. No field removal, CLI update, second stop,
warming/reactivation, Table seed, role/grant/resource/pool/price change or new
ledger is implemented. The four original slot identities and USD0.01792 aggregate
reservation remain inside the existing USD1/16-attempt program. Historical
synthetic seed values are not Azure wallet balances or another allocation.

## Private evidence required before prepare

The caller supplies the original/recovery/validation directories, a fresh
continuation directory and a sanitized rejection-evidence file. All are
canonical nonsymlink external paths; directories are owned mode700 and artifacts
owned mode600, bounded in size. The validation directory's original full-resource
`template.json` must match the full published `ffc9c3…` SHA-256. It is **not** the
template-only PATCH body and is never deployed by this capsule.

Coordinator must create the following sanitized captures from actual correlated
read-only Activity Log/provider/validation/what-if evidence. The author does not
invent or populate actual evidence. Reviewer independently checks its events and
no-commit classification; missing captures or inconsistent fields refuse prepare.

Rejection file schema:

```json
{
  "schema": "g1-api-rejection-v1",
  "api_version": "2024-03-01",
  "http_status": 400,
  "status": "Failed",
  "error_code": null,
  "problem_type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
  "problem_title": "One or more validation errors occurred.",
  "validation_errors": ["Unknown properties cooldownPeriod, pollingInterval in ContainerAppScale are not supported"],
  "unknown_fields": ["cooldownPeriod", "pollingInterval"],
  "no_commit_confirmed": true,
  "correlation_id": "actual correlated Activity Log ID",
  "event_id": "actual Activity Log event ID",
  "current_template_sha256": "semantic SHA-256 of actual unchanged old template",
  "expected_template_sha256": "same semantic SHA-256 from expected old template",
  "operation": "Microsoft.App/containerApps/write",
  "resource_id": "actual bound app ID",
  "recovery_prepared_sha256": "actual a prepared SHA-256",
  "update_consumed_sha256": "actual e update-consumed SHA-256",
  "proposal_sha256": "actual unchanged e proposal-file SHA-256"
}
```

`validation-dir/evidence.json` schema:

```json
{
  "schema": "g1-api-validation-v1",
  "api_version": "2025-01-01",
  "supported_api_versions": ["2025-01-01"],
  "validation_status": "Succeeded",
  "what_if_status": "Succeeded",
  "template_sha256": "actual full validation-envelope SHA-256",
  "proposal_sha256": "actual unchanged e proposal-file SHA-256",
  "validation_id": "actual response ARM deployment resource ID",
  "validation_id_kind": "response_id",
  "validation_result_sha256": "actual validation-result.json SHA-256",
  "what_if_id": "actual what-if request target URI",
  "what_if_id_kind": "request_target",
  "what_if_result_sha256": "actual what-if-result.json SHA-256",
  "changes": [{"resource_id": "actual bound app ID", "change_type": "Modify"}]
}
```

Include all actual what-if changes: exactly one Modify must target the bound
app; every other change must be Ignore. No Create/Delete/extra Modify is allowed.
The literal single-resource validation envelope's API, identity/location,
configuration/environment/workload and exact preserved template must match the
bound app/proposal. For this validation comparison only, a deep copy of live
configuration excludes exactly `ingress.fqdn` and `ingress.targetPortHttpScheme`.
All other fields remain strictly equal; neither live metadata nor the already
validated envelope/PATCH bytes are edited. Hashes distinguish that validated
envelope from PATCH bytes.

Actual rejection is ProblemDetails HTTP400 with **no provider error code**.
Preserve `error_code:null`; an inserted `InvalidRequestContent` value is not
observed evidence and is refused. `schema_validation_problem_details` in prepared
evidence is a **local classification**, not an Azure-supplied code. Status/title,
exact validation error, offending fields, correlation/event/resource/proposal
links and actual/expected old-template hashes are mandatory.

The validation directory also contains immutable owner-mode600
`validation-result.json` and `what-if-result.json`, hashed by `evidence.json`.
Validation reference kind `response_id` means the actual response supplied its
ARM deployment resource ID, not necessarily a unique invocation ID. What-if
reference kind `request_target` is the actual request URI: Azure supplied no
response ID, so it must not be described as a fabricated service-generated
operation identifier. The saved captures' `id`, `id_kind`, response key lists,
Succeeded state/status and exact what-if changes must match the evidence.
The full capture hashes and reference kinds are bound in prepared/results;
a reusable request target alone is not proof of a unique successful invocation.

## Read-only preparation and independent approval

```bash
.venv/bin/python scripts/quality/table_production_acceptance_continue.py prepare \
  --original-dir "$ORIGINAL_E" --recovery-dir "$RECOVERY_A" \
  --validation-dir "$VALIDATION_DIRECTORY" --rejection-evidence "$REJECTION_CAPTURE" \
  --artifact-dir "$FRESH_CONTINUATION_DIRECTORY" --executor-ip "$CURRENT_IPV4"
```

Prepare holds original execution/program and recovery execution locks. It
verifies exact consumed/failed `e`/`a` hashes, cold/drained/stop/absence/update
linkage, immutable original budget/proposal and zero case/restart/success files
or conflicting journals. Frozen helper/test/runtime/image and new capsule/test
hashes are bound. Current test/production configurations, secret versions/value
hashes, model/pricing/resource mapping, exact bound DENY configuration and
**all revisions inactive/all workers absent** are checked without warming.
The continuation-local `AllRevisionsAzure` wrapper injects `--all` exactly once
for every `containerapp revision list` call. It is constructed after frozen
read-only discovery and used throughout stopped preflight, successor/snapshot
and restart helpers. No frozen helper source or global module is patched.
In this stopped phase only, one bounded public GET may return403 or the known
inactive-route404;200 or any active/unknown revision or remaining replica is
refused. `prepared.json.stopped_route_proof` binds status, phase classification,
inactive revision names, zero workers and DENY policy. Apply freshly enumerates
all revisions/replicas and records its actual stopped proof again; no route
absence is treated as a live fence. Financial equality is explicitly
deferred until the successor reads the existing tables: absence is not a balance
snapshot. Expected account/cycle/legacy0 state is the bound old-drained map.

New `prepared.json` binds the complete prior hash manifests, corrected API,
evidence/envelope hashes, source/helpers, current projection, expected finances,
current executor IPv4 and unchanged four slots. No approval is authored here.
An independent reviewer supplies exactly this private approval schema:

```json
{
  "verdict": "approved",
  "packet_sha256": "new prepared.json SHA-256",
  "independent_reviewer": "different model/session",
  "api_version": "2025-01-01",
  "prior_hashes_sha256": "semantic SHA-256 of prepared.prior_hashes",
  "old_drained_sha256": "actual e old-drained SHA-256",
  "rejection_evidence_sha256": "actual correlated rejection capture SHA-256",
  "validation_template_sha256": "actual full validation-envelope SHA-256",
  "continuation_accepted": true,
  "unused_slots_verified": true,
  "stopped_old_writer_verified": true,
  "previous_executors_exited": true,
  "production_writer_paused": true,
  "staged_fenced_completion_accepted": true
}
```

## One-time apply

```bash
.venv/bin/python scripts/quality/table_production_acceptance_continue.py apply \
  --artifact-dir "$FRESH_CONTINUATION_DIRECTORY" --approval "$INDEPENDENT_APPROVAL"
```

- Hold original `execution.lock`, `recovery-program.lock`, new original
  `continuation.lock`, recovery-a execution lock and new execution lock. Recheck
  the complete stopped prefix/configuration/evidence. Exclusively fsync original
  `continuation-consumed.json` plus new own consumption before mutation. This
  guard blocks a second directory. Old recovery consumption remains intact.
- Append new `api-2025-update-consumed.json`; do not overwrite old
  `update-consumed.json`. Issue one template-only REST PATCH, API2025-01-01,
  via the byte-identical original `@update-proposal.json`. A failed/ambiguous
  response stops even if some successor later appears: no mutation retry.
- Observe sole ready current-image Table/min1/max1/single-worker successor,
  exact configuration/pins/effective hashes/retry0/command, explicit current
  debit/recovery fields and both account maps equal to old-drained. Current
  missing counters are never treated as legacy0; seed/cycle/reservation/financial
   drift stops before the first paid marker and is never repaired. Before any
   executor Allow write, require **live public403** under the original total120-second
   propagation deadline.404 is not accepted once the successor is ready.
- Write executor Allow once and observe200/ready with genuine total120-second
  propagation bounds. Four original ordered cases each consume their original
  marker once before HTTP; preserve numeric early observation. Every before map
  must equal last accepted finances. Require200/completed/clean SSE EOF, valid
  max64 input/max128 output usage, configured cached pricing, debit within the
  original slot and USD0.000002 balance/counter tolerance, unchanged other group,
  cycles/recovery and zero reservations. No retry/failover/substitution/recycling.
- After four passes: DENY once, observed403,100-second same-process/request/finance
  drain and one targeted restart. Actual container identity/count and process
  must change on the same approved revision with ready/effective configuration
   and both persisted balances/debit/recovery counters unchanged. Recheck **live
   public403** after restart before recording restart acceptance/results;404
   refuses completion. No extra inference.

The frozen recovery budget wrappers enforce30minutes overall,120-second public
waits and180-second worker/readiness/replacement observation including nested
CLI/HTTP and bounded cleanup. SIGALRM bounds synchronous helper calls with
cleanup headroom; repeated readiness observations are not paid/mutation retries.
Markers are exclusive, owned and fsynced; previous bytes are rechecked during
the run. Native CLI/HTTP error details remain withheld rather than leaking raw
body/keys; the bound correlation/status/error-code evidence identifies the prior
failure. No keys, prompts, outputs or raw console are committed/persisted.

## Results and outstanding gates

Success appends previously absent original `successor-baseline`, case,
restart and `results.json` files plus own journals/results. Original result
schema remains `g1-fence-recovery-result-v1`, with `original_apply_completed:false`,
four ordered case-result hashes, restart hash, original `recovery_link` and new
`continuation_link`, complete `prior_hashes`, source/helper binding and API evidence.
Own results additionally hash the original result file. Failures from `e` and
`a` remain unchanged; their existence is never relabeled as a successful apply.
Production's prerequisite reader must independently validate this chain and
actual four-pass/restart evidence, not accept file presence or this plan verdict.

On any fault retain actual current restrictive policy/markers/uncertainty; no
other automatic mutation, refund, row/seed reset, worker activation or original
apply/recovery replay. Success stays **test DENY/min1/max1**. Exact original
ingress/min0 cleanup is separate and must precede task cleanup completion;
ongoing minimum-replica spend is not bounded by the inference reservation.
Production remains memory/one and this capsule provides no production-account
coverage, migration or autoscaling acceptance.

The original local verification was42 passed /99.58% before compatibility fixes.
M1/M2 local verification was57 passed /99.61%. M3 local verification:
**63 passed /99.63% capsule coverage**; Ruff check/format and mypy pass. New hashes
are supplied at handoff. Type checking uses
the sibling script lookup that the CLI actually has:

```bash
MYPYPATH=src:scripts/quality .venv/bin/python -m mypy --explicit-package-bases \
  scripts/quality/table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_continue.py
```

Only mocks ran; no actual prepare, Azure/Docker/paid
calls, source/runtime edits or approvals. Sonar absent/N/A. Fresh full verifier,
independent contextual/exact review, actual prepare and approved continuation
remain gates. Frozen runtime/image evidence is reused by full hashes, not
relabeled as a new Docker/Azurite/Azure pass.

## Compatibility remediation and actual capture scope

M1 now matches the coordinator's observed null-code ProblemDetails rather than
requiring an invented provider code. M2 excludes only the two known read-only
ingress keys for the full-envelope comparison. Added tests accept that precise
shape and refuse invented codes, wrong ProblemDetails/no-commit/provenance,
any other configuration/template change and unknown reference kinds/capture
hashes. All original failure, consumption, proposal, helper/runtime and approved
`ffc9c3…` envelope bytes remain unchanged.

Coordinator reports read-only successful validation and exactly one bound-app
Modify/all other Ignore, with actual response and request-target references
saved under the approved private validation directory. Coordinator also reports
the previous full verification3060 passed /90.46%. These are handoff observations,
not author Azure/full-suite reruns. New source/test hashes require fresh verifier
evidence, independent re-review, fresh read-only prepare and exact approval;
the previous `b4417b…` binding cannot approve the corrected capsule.

## M3 inactive-route phase distinction

Coordinator's actual read-only continuation prepare `a` stopped before any
prepared/consumption/mutation/case record because its all-inactive/no-worker
route returns404 despite bound DENY configuration. It is not a live-route denial
failure. The capsule now distinguishes that precisely verified stopped phase
from live successor/after-four/restarted phases, which still require403. No old
warming, activation, second stop or generic404 propagation acceptance was added.

Tests cover stopped404/403 acceptance, stopped200 refusal, active revision with
zero workers and inactive remaining-worker refusal, and live404 rejection before
executor Allow/paid traffic and after restart. Existing M1/M2 ProblemDetails,
reference-kind/capture hashes, read-only exclusions and frozen source guards
remain unchanged. Coordinator reports the prior verifier3075 passed /90.46%;
this is not an author full-suite rerun. New hashes need fresh verifier/re-review,
fresh prepare `b` and exact approval before execution.

## M4 complete installed-CLI inventory

Installed CLI revision listing defaults to active-only; an empty default list
is not proof that inactive revisions or their workers are absent. Independent
exact review found three inactive zero-worker revisions while unconsumed C's
default-filtered inventory was empty. C is preserved but its incomplete proof
must not be carried into the next binding.

The local wrapper requests `--all` at the app-command boundary, so both explicit
stopped checks and frozen inherited `writers()` calls query every revision and
each replica set. Command inputs/target subscription/resource group are retained,
and an existing `--all` is never duplicated. Any hidden inactive worker refuses
prepare/apply before promotion, or successor acceptance before paid traffic.
Tests model the actual active-only default, record all three stopped revisions,
and verify `--all` during preparation, promotion and restart without broadening
M1/M2/M3 acceptance. Live403 checks and stopped-only404 classification remain.

Coordinator reports the previous63-focused/3081-full verification. New helper/
test hashes require affected verification, independent re-review and fresh
prepare D with the actual full inventory, then exact approval. No actual Azure
enumeration, prepare, mutation, paid call or old-artifact update was performed by
this author; original G1/recovery/runtime hashes remain unchanged.

M4 focused local verification: **68 passed /99.64% capsule coverage**; Ruff
check/format and mypy pass using the documented sibling-script type path.
Only mocks ran; no actual prepare, Azure/Docker/paid calls, staging or commits.
