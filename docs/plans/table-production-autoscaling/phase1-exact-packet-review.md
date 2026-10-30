# G1 exact prepared-packet review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra review session; not the harness author or executor.

The `c` and `d` assessments below are historical. **Latest verdict: exact `e` packet approved, zero unresolved Critical/Major findings.** See the appended [final `e`-packet approval](#final-e-packet-approval--2026-10-30). EP-M1 and EP-M2 are both resolved; no older packet is approved.

## Verdict

**Not approved for execution. Critical: 0. Major: 1 unresolved (EP-M1).**

The concrete packet's source, credentials, models/budget, isolated resource ownership and staged restoration disposition passed the checks below. A newly reproduced deactivation-transition defect must be corrected before execution. **No private `approval.json` was created.** This review does not authorize Azure mutation, inference, stop/update/restart or production changes.

The final verifier rerun for the compressed-transport hashes was reported in progress. The verification document inspected during this review contained the previous `b0a306…`/`3ec4db…` revision's 83 focused tests, 96.93% harness coverage and 2,970 full tests/90.46% source coverage. Those results are not relabeled as a fresh final-hash verification. Even a passing final rerun would not close EP-M1 without the transition fix and its regression evidence.

## Exact binding

Prepared artifact: `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/table-prod-g1-20261030-c/prepared.json`.

| Artifact | SHA-256 |
| --- | --- |
| Private `prepared.json` | `ed400ad09fa49e2d4ea7c80235fa9fddbbbfbed4f6492008e33d42da6792ce69` |
| `scripts/quality/table_production_acceptance.py` | `35e082c537bc144a59f3ad321175deec31ef0770360ccc856e1f44bc04c97e30` |
| `tests/unit/test_table_production_acceptance.py` | `affa20a3e2d0dbfbfb5dd7fc2cf9d0bef714f7c88bd5d680877ffbd29af3d50a` |
| `docs/plans/table-production-autoscaling/phase1-packet.md` | `8143d2da28a55943e839cb2207c428db2ed073a39ed09af25d51bf69433c02bf` |

The artifact directory is owned by the reviewer/executor user and mode 700; `prepared.json` is mode 600. It contained only `prepared.json`; the bound fresh program-ledger path did not exist. There were no consumption, stop/update/restart or paid-call artifacts. `source_binding` matched all 78 runtime/build/dependency-manifest entries and the current helper/test pins. The target is the production immutable digest `sha256:36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4`; production itself is not a mutation target. The isolated original image is `sha256:78c5d570d64eacfdcad02c8c8c21c46a4db24af2c4ce944c687a01c99410fb6a`.

## Major finding

### EP-M1 — Absence polling rejects the expected inactive/draining transition

- **File/Module:** `scripts/quality/table_production_acceptance.py:125–142` (`Azure.writers`), `:631–644` (`wait_writers`), and `:976–985` (deactivate then wait); the fake deactivation at `tests/unit/test_table_production_acceptance.py:556–577` immediately removes workers.
- **The Issue:** After a successful revision-deactivate command, revision metadata can report inactive while replica termination is still in progress. `wait_writers(absent=True)` calls `writers(allow_none=True)`, which first rejects *any* inactive revision with replicas. `allow_none` only permits zero replicas; it does not permit observing draining replicas. The loop therefore raises on its first such observation instead of waiting for their actual disappearance. Command completion is not established evidence that all replica metadata and background writers have already vanished; no such guarantee is bound in this packet.
- **Why Static Analysis Missed It:** The steady-state active-writer check is correct for snapshots/admission. Its reuse during a deliberate stop transition is the contextual mismatch, hidden by tests that model deactivation and worker disappearance atomically.
- **Impact:** The run can consume its ledger/stop marker, fence the app and deactivate the old revision, then stop on a normal transitional state. The successor is correctly prevented from starting, so this is **not an overlap or overspend bypass**. It is nevertheless a material orchestration defect: the single-use operation is stranded after mutation and needs separate recovery instead of completing the reviewed bounded stop sequence. A safe refusal for unexpected drift does not justify making an expected drain state an immediate failure.
- **Recommended Fix:** Add a narrowly scoped absence-observation path that enumerates all actual replicas, including those belonging to inactive draining revisions. Keep them counted as remaining workers and continue bounded polling. Preserve strict active/sole-writer checks for normal snapshots, cold-start readiness and successor/paid admission. Do not filter inactive replicas out, treat inactive as absent, reactivate the old revision, retry deactivation, or start the successor until **all replicas are absent and no revision is active**. On deadline or genuine conflicting state, retain the existing stop/recovery behavior.
- **Required regression:** Observe active/one before deactivation, inactive/one draining for one or more polls, then inactive/zero. Assert no update while any old replica remains, eventual progress only after zero workers/no active revisions, and timeout without update when the draining replica persists. Retain existing overlapping-active-revision and inactive-worker rejection tests for steady-state calls.

**Independent local reproduction:** With real `Azure.writers` and `wait_writers`, mock only `app_command` to return one inactive old revision and one draining replica. `wait_writers(absent=True)` immediately raised the literal `Inactive revision has workers` after exactly one revision-list and one replica-list read. No sleep/retry interval or absence success was reached. This was a no-network, no-file `python -B` check; it does not claim to have observed Azure deactivation live.

## Checks completed

### Source, transport, launch and state

- Actual packet hash, helper/test hashes and all 78 source-manifest pins matched locally. Existing coordinator in-image verification covers the same 76 runtime Python files; this reviewer did not rebuild or rerun Docker.
- The compressed command is **1,135 characters** and round-trips to the unchanged `SNAPSHOT_PROGRAM`, SHA-256 `6f4c0dbce56e78b5611c687ab1f5121c9e7cf28976b05a262190046fce1e10e2`. The updated mocked PTY test passed independently, checking command shape, exact bytes, target arguments, redaction and unique structured output. Neither 1,135 nor the test's 1,800-character bound is asserted to be an Azure platform limit.
- Live test and production app projections matched their private bindings. Both use a single container, `Single` revision mode and max1. The test starts min0 with public HTTPS and no explicit IP restriction; production is min1/max1 memory-backed. No command/argument overrides or non-`FOUNDRY_` app environment entries were present in either binding/live resolution. In particular no `WEB_CONCURRENCY`, `UVICORN_*`, `GUNICORN_*` or other app worker override is present.
- The prepared old process's command hash exactly matches the pinned Docker `ENTRYPOINT` argument vector, including the null-terminated `/proc` representation. That entrypoint has no worker-count/reload override. Current read-only replica enumeration found **one** test writer matching the prepared revision, container identity and restart count. Process-start ticks are supplied by the coordinator's prepared full snapshot; this reviewer did not execute another snapshot.
- Prepared local readiness is true and two canonical accounts are quiet, with zero active reservations/inflight. Both cycle starts are `2026-10-01T00:00:00+00:00`; observed remaining estimates are USD 99.96840999999999 and USD 99.99898. Legacy debit/recovery counters are bound as zero, not reconstructed historical totals. The 100-second drain, unchanged-account checks, counter-baseline checks and corrected per-case financial chain remain in place. Current Table coordinates match resolved settings; no Table writes, resets, seeds or grants were performed by this reviewer.

### Credentials and resource identity / S2

- Resolved pinned secrets silently through the harness's version-pinned Key Vault path. All **eight test and eight production secret pins/value hashes** matched. Effective test environment hashes matched the prepared process snapshot. Current mode/model/pricing/Table coordinates matched. No credential, raw Key Vault value, prompt or model output was printed or stored.
- A first single-subscription account inventory resolved the dedicated test resource but could not resolve production endpoints. That incomplete check was not treated as success. Read-only inventory across **four enabled accessible subscriptions** then resolved every configured production Azure host to exactly one management resource ID.
- Both `fs-openclaw.openai.azure.com` and `fs-openclaw.services.ai.azure.com` resolve to the **same `fs-openclaw` resource ID**. Both `fs-swarm.openai.azure.com` and `fs-swarm.services.ai.azure.com` resolve to the **same `fs-swarm` resource ID**. Production's other hosts are `opencode.ai` and `openrouter.ai`, representing preserved non-Azure providers, not additional Cognitive Services resource IDs.
- The bound `af-opencode-agents.openai.azure.com` endpoint resolved to exactly the prepared **`af-opencode-agents` AIServices management resource ID**. Its full case-normalized ID is distinct from **both production Azure resource IDs**, not merely from their DNS names. Thus IR-S2's direct management-identity requirement is satisfied for this packet, including endpoint aliases.
- Nonsecret SHA-256 fingerprints of the case-normalized IDs: test `d80b8475ef51f15d84bc266d2d6b0460459da156bbeafe3414f001abd4fd0e6b`; production set `30d9b377b950db10c8059f06431e56cebc4cdf8728c3fc1b32d6de4da2995961` and `f6a18660bae1996088c256d483122da0c2b0a38cc950cb85887938335944371a`. Full IDs remain private; none are invented here.

### Cases, liability and restoration

- Exactly four ordered cases: `gpt-6.1-sol` nonstream/stream, then `gpt-6-luna` nonstream/stream. Each has one selected metered backend and its bound canonical test account; aliases and alternative pool backends are absent. Current-source estimator output is USD 0.00393 per case; the conservative reservation is **USD 0.00448 each / USD 0.01792 total**. Synthetic test pricing is USD 10 input/USD 30 output per million, not an Azure price/balance assertion.
- The fixed minimal text request has max128 output and a 64-input reservation allowance. The reviewed successor sets retries to zero; there is no case retry/substitution, no budget recycling and no post-output failover. Incomplete reasoning output or a deadline failure is a stop, not permission to enlarge the request or spend another slot.
- The fresh **USD 1 whole-program / 16-attempt** authorization is independent liability on the dedicated resource, outside production's four account allocations. G1 consumes at most four attempts and preserves unknown reservations. Historical synthetic USD 100 rows are delta baselines only. This packet covers zero production inference accounts and no non-Azure paid calls.
- Explicit staged completion is acceptable: successful G1 ends with the test app **deny-all fenced, min1/max1**. Exact original ingress/min0 restoration is **not completed by this script** and needs a separate reviewed cleanup transition; do not reactivate a stale revision or reset balances. Failure leaves the current restrictive state and consumed records for fresh-state recovery.

## Approval-file disposition and next gate

No approval JSON exists from this review at `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/table-prod-g1-20261030-c/approval.json`. The structurally acceptable bindings and liability/restoration decisions above do not override EP-M1.

Correct only the absence-transition observation and add the targeted regression. Then obtain final verifier evidence for the corrected source/test hashes, prepare a **fresh** packet without overwriting/replaying this one, and independently review that exact binding before writing executable approval fields. All prior single-use artifacts remain immutable. Min0 may scale away while review is pending: apply must still require the same old process and actual sole writer before consumption; if that guard fails, use fresh preparation/review rather than weaken it or warm a replacement into the old approval.

Only the coordinator may later apply a fully approved packet. This reviewer performed read-only Azure metadata/secret-hash checks and local mocked checks, not prepare/apply, Azure mutation, provider inference, deployment or restart. Sonar remains absent/N/A. Production remains memory-backed with max1.

## Current d-packet assessment — 2026-10-30

**Not approved for execution. Critical: 0. Major: 1 unresolved (EP-M2). EP-M1 is resolved. Final verification passed. No private approval JSON was created.**

Prepared artifact: `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/table-prod-g1-20261030-d/prepared.json`.

| Artifact | SHA-256 |
| --- | --- |
| New private `prepared.json` | `825f37c524db70a46e21864ba917a3cbb7e01d982760885a970f6a50611a2423` |
| Harness | `c56e8ce97cde14a48011dc24384c5cab0500851216012a3b1c96d8cf446cb20d` |
| Tests | `2565ab3684e97adc612c97a96d909db5cfd4befa89b7529ce16ba251102d7116` |
| Packet document | `be271e4aa59ddf548b16139b0257c8eb403cc2ac3f89edbe937ed0648cd996f0` |

### Resolved transition and refreshed exact bindings

- **EP-M1 resolved:** harness lines 125–149 allow inactive draining replicas only through the explicit `allow_draining` mode; this additionally requires every revision's `active` value to be exactly false. Lines 638–656 use it only for deliberate absence polling and return only for an empty aggregate replica list. All revisions' replicas remain counted; there is no inactive-replica filtering. Normal readiness/snapshot/replacement guards remain strict. The final independent no-active-revision check at lines 991–997 remains before the update marker and mutation.
- New targeted regressions cover active/one → multiple inactive draining revisions → inactive/empty, all-revision enumeration, persistent-drain timeout without update, unexpected active revision without update, and preserved steady-state/readiness/replacement refusal. The two no-file draining-enumeration and strict-guard tests passed when invoked independently with mocks. The complete 87-test verifier run includes the two no-promotion orchestration cases.
- Both `c` and `d` packet hashes were checked; both directories were still owner-only mode 700 with only their mode-600 `prepared.json`. Neither bound ledger existed. All 78 source-manifest entries and new helper/test bindings matched.
- Direct comparison showed `d` preserves `c`'s image, resource/app projections, all secret pins, cases/prices/reservations, Table coordinates, original account state, ingress/minimum, executor IP and dedicated-resource binding. Effective environment and server-command hashes in the prepared snapshot also match. The earlier direct cross-subscription resource-ID disjointness evidence therefore applies to these unchanged identities; it was not replaced by a DNS-only assertion.
- Fresh read-only app metadata matched both `d` projections. Fresh strict test replica enumeration found one writer matching `d`'s prepared revision/container identity/restart count. The prepared full snapshot is ready with two quiet accounts and unchanged canonical financial state. No additional exec, provider request, prepare/apply or secret-value display occurred in this follow-up. These are point-in-time observations; apply's same-process and quiet-state guards remain mandatory.
- Four cases retain **USD 0.01792 total reservation**, max128 output, zero retries and separate dedicated-resource liability. Staged success at **test min1/max1 plus deny-all ingress** is explicitly acceptable, with original ingress/min0 restoration and task cleanup deferred to a separately reviewed transition. Production remains outside the mutation scope.

### Final verification evidence inspected

All logs below are under `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/`:

| Log | Completed result |
| --- | --- |
| `phase1-epm1-final-focused.log` | 87 passed, 15 warnings, 0.58 seconds; harness 557 statements, 17 missed, **96.95%** |
| `phase1-epm1-final-full.log` | **2,974 passed, 21 skipped**, 8,969 warnings, 58.30 seconds; source **90.46%** |
| `phase1-epm1-final-ruff-check.log` | All checks passed |
| `phase1-epm1-final-ruff-format.log` | 78 files already formatted |
| `phase1-epm1-final-mypy-src.log` | No issues in 76 source files |
| `phase1-epm1-final-mypy-harness.log` | No issues in one source file |

These concrete final logs clear the prior pending-verification gate for the listed frozen hashes. They do not test or cure the external Azure CLI normalization below. No verification job was polled or rerun by this reviewer; the full-log search was narrowed to its completion summary after the first search matched ordinary test names containing “failed.”

### EP-M2 — Known CLI normalization changes the outgoing successor template

- **Severity:** Major.
- **File/Module:** Harness `scripts/quality/table_production_acceptance.py:999–1015`; [historical isolated deployment evidence](../table-write-metadata/evidence.md), lines 40–43; installed Azure CLI 2.91.0 `azure/cli/command_modules/containerapp/custom.py:393–398, 434–456, 710–712` and `_clients.py:145–157`.
- **The Issue:** The harness still performs `az containerapp update --image ... --min-replicas 1 --max-replicas 1 --set-env-vars FOUNDRY_RETRY_ATTEMPTS=0` after permanently stopping the old writer. The currently installed CLI unconditionally adds `value: ""` to every existing environment entry lacking `value`, including all eight secretRef-only entries in this exact app. Its update builder then copies those modified containers into the outgoing template and `_clients.py` sends that envelope with `PATCH`/`json.dumps`. This is an outgoing request-body transformation, not just CLI pretty-printing. Historical evidence records this same isolated app's binding failure and a scoped ARM patch needed to restore exact configuration before traffic.
- **Why Static Analysis Missed It:** The behavior is in the installed external CLI implementation and the app's concrete secretRef-only shape, outside harness mocks. Existing tests model ideal configuration preservation rather than the actual update serializer.
- **Impact:** The known unwanted environment shape can be persisted or echoed into the successor metadata, causing strict `verify_successor` to reject after old-writer shutdown and update consumption. Runtime precedence for mixed empty-value/secretRef entries is not proven here and must not be assumed equivalent. The correct fail-closed check prevents paid traffic, but this avoidable known write-path drift strands another single-use run after mutation.
- **Recommended Fix:** Replace only this high-level update with one scoped direct ARM `properties.template` PATCH built from the already bound, raw original template. Preserve secretRef-only entries exactly; change only reviewed image, retry=0 and minimum=1 (max remains the bound 1, with already-reviewed revision naming handling). Build from Azure metadata, **not** the redacted projection or resolved secret values. Keep ingress/configuration/identity preservation, consume-before-mutation, all-old-worker absence, bounded readiness and the existing exact successor/environment/secret checks. Do not silently discard drift or add a post-failure repair/retry path.
- **Required regression:** With a realistic secretRef-only environment fixture, capture the single outgoing PATCH and assert no `value` key is added to those entries, no resolved credentials enter the body, and all non-reviewed template fields are preserved. Assert no PATCH before confirmed absence and that genuinely changed successor references/values still refuse. Existing tests can be adapted; no new feature or resource is needed.

**Evidence:** Resolved `/opt/homebrew/bin/az` to installed `/opt/homebrew/Caskroom/azure-cli/2.91.0/libexec/bin/az` and inspected the above local source without invoking an update. An in-memory check using the bound redacted app shape passed the intended image/retry/min successor comparison; adding the installed CLI's empty-value transformation to its eight secretRef-only entries then raised `Successor app configuration drift`. No Azure mutation or secret output was used to establish this finding.

### Current approval disposition

`/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/table-prod-g1-20261030-d/approval.json` **was not created**. EP-M1 and verification are closed; EP-M2 is the only unresolved Major. Apply the narrow template-write correction, verify that delta and bind/review a fresh packet without overwriting `c` or `d`. No additional documentation artifact or unrelated feature is requested. The separate liability and staged fenced/min1 completion decisions remain accepted; they are not permission to execute the currently blocked update path.

## Final e-packet approval — 2026-10-30

**Approved for the exact single-use isolated G1 sequence. Unresolved Critical: 0. Unresolved Major: 0. EP-M2 resolved.** Reviewer session: `ses_e732da5f9ffe65dbkBpH7RZe9E` (independent GPT 6 Astra reviewer, not the developer/executor).

Prepared artifact: `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/table-prod-g1-20261030-e/prepared.json`.

| Binding | SHA-256 |
| --- | --- |
| Exact private packet | `721fc9be3e5a862741e3c71eaa327dc8c0e153c789ee0a17029af4ee13a9e8de` |
| Harness | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` |
| Tests | `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |
| Packet document | `59d486b5a459260f2a6f0e82e5a0f2cb084f97f47096481a677915ecfc1f4d5c` |
| Template proposal semantic hash | `8d27348edaac731e67129785a2a5b85c93546fbd803eebad6215a76e68646a2c` |

### EP-M2 closure and concrete proposal

The only successor write is now one direct REST PATCH of `properties.template`, sent via an owner-only private body file. `template_proposal` deep-copies the original raw metadata and preserves every unrelated environment entry/resource/rule, including all eight secretRef-only entries without adding `value`. It changes the reviewed image, retry=0 and min1/max1 and removes the old revision suffix so Azure can generate one. It never incorporates resolved Key Vault values or substitutes the redacted projection as a deployable template.

The pure `verify_template_proposal` enforces template-only scope and reuses the unchanged strict successor predicate. Prepare binds its semantic hash. Apply validates the proposal before any consumption, persists exclusive mode-600 proposal/binding artifacts under the mode-700 directory, and checks original template equality, exact proposal bytes and proposal validity again after all old workers are absent. Only then does it durably consume the update and issue `az rest --method patch --body @<private-file>`. No `containerapp update`, normalization bypass, repair retry, identity/ingress patch or broader resource change was added. Successor configuration, credential/environment, financial and readiness checks remain mandatory.

Independently reconstructed the actual body from freshly read live app metadata: it matched the packet's semantic hash, left the source metadata unchanged, contained only `properties.template`, and preserved all eight secretRef-only records exactly. Independently invoked nine no-file tests covering proposal preservation, six unauthorized changes and retained absence/readiness guards: **all passed**. The full mocked suite also covers REST-only orchestration, durable proposal/update markers, no PATCH before absence, and malformed proposal rejection before consumption.

### Refreshed exact checks

- Verified packet/source/test/document hashes and all 78 runtime/build source pins. The unchanged production image remains `sha256:36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4`.
- Compared `e` with the independently reviewed `d` binding: app projections, image, all secret pins, models/cases/prices/reservations, Table coordinates, original quiet accounts, ingress/minimum, executor IP and dedicated resource identity are unchanged. Prepared process environment and command hashes agree with the prior verified launch. The earlier full management-ID disjointness check across four subscriptions therefore remains applicable: dedicated `af-opencode-agents` is distinct from both production Azure resources, including their endpoint aliases.
- Fresh read-only test/production metadata matched the bound projections. Strict test enumeration found **one actual writer matching the new prepared revision/container identity/restart count**. The prepared full snapshot reports readiness and two quiet canonical accounts. Original min0 and unmodified public ingress are captured; the no-worker-overlap, same-process and quiet-state rechecks before consumption remain enabled.
- Prior `d` remained unchanged/unconsumed. Before approval, `e` contained only its mode-600 packet in an owned mode-700 directory; its fresh program-ledger path did not exist. No consumption or paid-call record existed. This reviewer did not call prepare/apply, exec, provider inference or any Azure mutation.

### Completed final verification

Inspected completed logs in the approved temporary directory, with prefix `phase1-epm2-final-`:

| Log | Actual result |
| --- | --- |
| `focused.log` | **95 passed**, 15 warnings, 0.55 seconds; 587 harness statements, 17 missed, **97.10%** |
| `full.log` | **2,982 passed, 21 skipped**, 8,969 warnings, 57.91 seconds; **90.46%** source coverage |
| `ruff-check.log` | All checks passed |
| `ruff-format.log` | 78 files already formatted |
| `mypy-src.log` | No issues in 76 source files |
| `mypy-harness.log` | No issues in one source file |

These are observed verifier outputs for the supplied frozen revision, not guessed counts or reviewer full-suite reruns. Sonar remains absent/N/A. Existing immutable-image and Azurite evidence remains applicable to the unchanged runtime; live REST promotion and G1 outcomes are not claimed passed.

### Approved scope and private record

Approve only this packet's single-use fence/drain, old-writer stop/absence proof, exact template promotion, **four sequential cases reserving USD 0.01792**, final fence/drain and one actual verified restart. The broader program ceiling remains USD 1 / 16 attempts; G1 permits four, with max128 output, zero retries and retained unknown liability. Authorization is on the dedicated test resource, outside production's four account allocations. Historical USD 100 synthetic rows remain debit-delta baselines, not funds or reset permission. No production mutation or non-Azure provider call is approved.

**Staged fenced completion is explicitly accepted:** successful G1 leaves the test app deny-all fenced at min1/max1. Restoring captured original ingress/min0 and task cleanup requires a separate reviewed transition and must not be represented as completed by G1. On drift, process replacement, unexpected state or ambiguous failure, retain consumed records and the script's stop behavior; approval does not permit replay, stale reactivation, seed reset or an unreviewed repair. Min0 may scale down before apply; the same-process gate must still refuse rather than weakening the binding.

Private executable approval: `/private/var/folders/yb/v29g2l750ms2bky383fkb6j00000gn/T/opencode/table-prod-g1-20261030-e/approval.json`, with the exact packet hash, reviewer session, `verdict: approved`, `m1_closed: true`, separate-liability disposition and `staged_fenced_completion_accepted: true`. Approval applies only while the harness's complete source/metadata/credential/process/financial binding checks pass. This record is authorization, not evidence of execution or production cut-over.
