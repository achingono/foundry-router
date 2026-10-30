# G1 API continuation independent implementation review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra subagent session, separate from the implementation author and executor.

## Verdict

**Approved implementation and exact single-use packet D. Unresolved Critical: 0. Unresolved Major: 0.**

M1–M4 are resolved in the current candidate. Final verification and independent exact D checks passed; private D approval was created and validated. See the [exact review](exact-packet-review.md) for the complete binding and narrowly approved lifecycle. Earlier blocked verdicts and findings below are historical; packet C remains unapproved and unchanged. Approval is not an executed G1 result.

## Final M4 resolution and exact D approval

Current hashes: runner `a2b3e20c24141528ff92560c9675eebb6289a29339bb51257ea16566724280ee`; tests `c912b9f8eaa93f1066819999cc8e19a8897d130a528ebb5b5d240708375b1191`; packet `43fe06467626fbe9ceab6898b8b87966d098c9a8be3bc154ac338b8d0b669677`. Prepared D: `b9cc205e8c3c782e4c71371e00f93ea61d2e9170de2c7d320a38ac2baa310c4b`.

Reviewed the M4-only diff. `AllRevisionsAzure.app_command()` copies arguments and injects `--all` exactly once for revision listing, preserving the app/subscription binding. `stopped()` returns that wrapper, so inherited frozen worker, snapshot and restart helpers also enumerate inactive revisions. Frozen helpers remain byte-identical; there is no global monkeypatch or extra mutation. Tests now model the CLI's active-only default, bind three inactive revisions and reject hidden inactive workers during prepare, apply preflight and successor acceptance. M4 is resolved; no additional Critical/Major issue was found in this delta.

Independently refreshed D under original execution/program and recovery execution locks. All three actual revisions were explicitly inactive with zero workers; bounded public GET returned404 under unchanged bound DENY configuration. Full revision inventory and configuration were rechecked after the GET and matched D. Original/recovery manifests, four unstarted slots, unchanged evidence and expected old-drained finances matched; current balances remain correctly deferred until successor startup. Full runtime/image provenance and silent test/production secret-value hash/pin comparisons passed. Reconstructed the raw old template from its original hashed projection again and matched the unchanged rejection capture. M1/M2/M3 behavior and evidence bindings remain intact.

Inspected completed `continue-m4-final-*` logs once available: **68 focused passed /99.64% capsule coverage;3,086 full passed,21 skipped /90.46% source coverage**. Ruff lint/format and source/operator mypy passed. No redundant tests were run. Frozen source, prepared and evidence hashes were checked again under locks immediately before approval creation; original/recovery history remained unchanged afterward.

Created exclusive fsynced mode600 D `approval.json`, accepted by the capsule's exact validator, SHA-256 `e6cec55ff50e1ed00b990c33a7330d4414e2654de271a51eb66bdb17fdddd59e`. Executor-exit and production-writer-pause acknowledgements use the coordinator's explicit handoff plus available original/recovery locks and preserved failed histories; private production drafts were not independently inspected. This author performed no apply, Azure mutation, inference or restart.

## Historical candidate / exact C review — M4 blocked approval

Independently verified current runner `c7068b1edb935e5497de1fbaaa303e13f21e743d0a779ecfec899f5a2981f684`, tests `d105aa96ca3c871d3d4bfcb5efec3914189ab3eef357917526fd1979d8cfbc6d` and packet `6e627185ff56d8ab156237b8b69ddc1c1440cb0656ef00a6c1f4ff748a44dc9d`. Packet C is `efdd351de448708edf79b2c120a873741b731c4709cad8ff9591cba5d8a372c8`.

M1's null-code ProblemDetails and evidence hashes, M2's exactly two read-only exclusions, and M3's stopped404/live403 separation were re-read in the final source/tests. Live403 now precedes executor Allow and follows restart; stopped200 fails. M1/M2 compatibility checks passed against C's actual sanitized captures and refreshed live configuration. The corrected raw-template hash domain was independently reconstructed from the original projected template using hash-checked current literal values. The earlier projected-domain capture remains separate. M3's route-status defect is resolved; M4 below concerns the completeness of the prerequisite enumeration, not accepting404 generically.

Inspected completed verifier logs and independently recomputed their documented hashes: **63 focused passed /99.63% coverage**, **3,081 full passed /21 skipped /90.46% source coverage**, Ruff lint/format and source/operator mypy passed. Tests were not redundantly rerun. Existing mocks do not model the CLI's default active-only revision filtering.

### Major M4 — `revision list` omits inactive revisions without `--all`

- **File/Module:** Current `scripts/quality/table_production_acceptance_continue.py:204–215,218–242`; stopped-route evidence in C.
- **The Issue:** `inactive_revisions()` calls `azure.app_command(["revision", "list"])`. Independently running the installed CLI's local help confirmed `--all: Show inactive revisions`. The default list therefore does not establish that all revisions were enumerated. When no revision is active, an empty list makes `all(...)` true and executes no replica queries. C's proof contains `revision_names: []` despite three existing inactive revisions.
- **Independent reproduction:** Under original execution/program and recovery execution locks, a read-only `revision list --all` plus replica listing for every returned revision found **3 explicitly inactive revisions,0 active,0 unknown activity and0 workers**. The prepared proof lists0 revisions. Actual current zero workers is independently observed, but the executable will repeat the incomplete query at apply. This point-in-time manual check does not repair its acceptance predicate or prepared proof.
- **Why Static Analysis Missed It:** The code and mock list look structurally correct; the omission depends on the installed Azure CLI's default filter. Tests return fixture revisions without reproducing that filter.
- **Impact:** An inactive revision with a draining worker can be omitted and the capsule can claim all old writers absent, then promote before verifying the required writer-exclusion boundary. It also binds an incomplete revision inventory as proof. This violates the explicit all-revisions/zero-workers precondition even though the three currently observed inactive revisions happen to have zero workers.
- **Recommended Fix:** Make the continuation-local enumeration explicitly request `revision list --all` and query replicas for every returned revision while retaining explicit `active is False` and zero-worker checks. Preserve the frozen original/recovery files. Add a CLI-argument-sensitive fixture/test in which default listing hides inactive revisions and `--all` returns them; prove an inactive draining worker refuses prepare/apply before consumption or promotion, and that truly stopped inactive revisions are included in the bound proof. Retain active-zero-worker/unknown-status and stopped/live HTTP tests. Reverify changed bytes and prepare a fresh packet with the real full inventory; preserve C and all prior history rather than editing its prepared bytes. Independent exact approval remains required.

Only review documents were written. Read-only metadata and silent secret-value/hash comparisons were performed; no apply, inference, Azure mutation or private approval creation occurred.

## Earlier follow-up — fully stopped app returns404 (historical M3)

Independently recomputed current hashes:

| Artifact | SHA-256 |
| --- | --- |
| Continuation runner | `8d82c443cdff7f8ab8bd1f24f2bc782c887b210b7dc2155fce94c7c1436d6fa7` |
| Continuation tests | `0c5c07f4567f9bf4f1ab2da092a41263dd5e1c34f6986818a80d3030990bd79b` |
| Operational packet | `73cc97532614ad0687b60dbf32531c72401902b582edf042bbe16a4d8d60c87e` |

**M1/M2 follow-up:** Source lines223–252 now require null provider code and explicit ProblemDetails/provenance/unchanged-template evidence. Lines284–296 deep-copy live configuration and remove only the two named ingress read-only keys before strict comparison. Tests486–572 exercise truthful acceptance, invented code/problem rejection, other configuration drift and reference-kind/capture-hash rejection. Source lines299–363 and the packet now distinguish validation response IDs from what-if request targets and bind capture hashes. These changes resolve the identified source-contract defects; this follow-up inspected them but did not rerun tests or independently inspect private captures. The ongoing verifier must report completed results. The original findings below are retained as historical findings against `b4417…`, not descriptions of current predicates.

### Major M3 — Active-route403 is required after all routes have been deactivated

- **File/Module:** Current `scripts/quality/table_production_acceptance_continue.py:203–212,367–387,550–582`; frozen recovery `public_wait_async()` at177–203; frozen original `Azure.writers()` at126–150.
- **The Issue:** `stopped()` first requires `writers(allow_none=True, allow_draining=True)` to find no workers. That helper also requires **every revision's active flag to be explicitly false**, not merely zero replicas. It then unconditionally calls `r.public_wait(...,403)`. The frozen waiter rejects404 as `Unexpected recovery public status`. Coordinator reports the actual bound-origin GET now returns404 with the original DENY policy present, every old revision inactive and no workers. This route-absent state cannot satisfy the current predicate. The current post-promotion sequence verifies metadata/readiness/finances and then writes executor Allow without first observing403 from the newly available route.
- **Why Static Analysis Missed It:** The helper is valid for an active route. Mocked403 while revisions are inactive does not model the observed lifecycle-dependent public response.
- **Impact:** Truthful read-only prepare stops before writing its new prepared packet. Treating this as authorization to warm/reactivate an old worker would violate the stopped-prefix plan. Globally accepting404 as fence proof would instead weaken live-route gates and could mask a missing or wrong route.
- **Recommended Fix:** Add a continuation-local, bounded stopped-state observation accepting403 or the specifically observed404 only after verifying the bound origin, unchanged old configuration/pins and exact control-plane DENY policy, **all revisions explicitly inactive**, and zero workers across all revisions. Reconfirm the stopped/configuration predicates around a404 observation before accepting it, so stale pre-observation metadata cannot alone justify the exception. Reject200 immediately; do not use the frozen propagation helper's transient200 behavior for this preflight. Preserve fail-closed behavior for unknown revision activity, active-but-zero-worker state, draining workers, configuration drift and other unexpected statuses. Bind the actual observed status and its stopped-state basis in preparation evidence;404 means route absent under the verified stopped conditions, not an observed ingress denial or proof of finances.
- **Live-route boundary:** After the one approved promotion establishes the sole ready current-image successor, exact configuration/pins and expected financial baseline, observe bounded403 at the same bound origin **before consuming/writing executor Allow or any paid marker**. Keep the live final-DENY403/drain requirement, and confirm403 again after the actual restarted worker is ready before declaring fenced success. The stopped-state404 exception must never satisfy a promoted/restarted live-route fence check. Keep absolute deadlines, frozen helpers, one-time mutation counts and all financial/history guards; no warming, reactivation, new stop, template change, refund or mutation retry is warranted.
- **Required Verification:** Add a realistic no-route404/strictly-inactive success case for read-only prepare and apply preflight, plus refusal for active-with-zero-workers, unknown activity, draining worker, missing/changed DENY and HTTP200. Assert no prepared/consumption/mutation on invalid preflight. Test actual prepared status/basis binding and rechecks, successor403 ordering before Allow, and failure/timeout or404 at live fence stages with no inappropriate advancement. Preserve bounded observation/cleanup tests. Update the packet/plan's phase-specific fence wording and obtain independent review of the revised bytes.

**Reported execution history:** Coordinator reports the attempted real read-only prepare failed with `Unexpected recovery public status` before new `prepared.json` or consumption, and that all original slots remain unstarted with no mutation or paid call. Source ordering corroborates that this error from `stopped()` precedes `h.create(prepared.json)`; this reviewer did not independently enumerate the private directory or query Azure. Preserve that failed preparation record honestly and revalidate the actual inventory/locks/source before a later preparation. It is not a consumed promotion, a G1 result or an executable approval.

## Historical M1/M2 findings from actual-evidence compatibility review

The coordinator reports the actual response/envelope shapes below. This reviewer re-read the unchanged implementation and packet and verified their comparison behavior; the private captures themselves were not independently inspected in this follow-up. These findings therefore distinguish coordinator-observed Azure facts from independently confirmed source defects.

### Major M1 — Rejection contract requires an unobserved Azure error code

- **File/Module:** `scripts/quality/table_production_acceptance_continue.py:217–236,301–310`; `packet.md:46–63`.
- **The Issue:** Line223 requires `error_code == "InvalidRequestContent"`. The coordinator's actual Activity Log `statusMessage` is a ProblemDetails object with `type`, `title`, `status`, `errors`, and `traceId`; HTTP400/title `One or more validation errors occurred` and `errors['$']` identify the unknown `cooldownPeriod`/`pollingInterval` fields. No Azure error-code field was observed. A truthful null code fails the predicate; an omitted code raises `KeyError`. The packet currently prescribes the same unsupported literal.
- **Why Static Analysis Missed It:** The expression is type-correct and synthetic fixtures manufacture the required code. Passing tests do not establish the actual provider response schema.
- **Impact:** Truthful preparation is blocked. Populating the demanded code would invent provider evidence and invalidate the approval chain.
- **Recommended Fix:** Permit an explicitly null provider code for the observed ProblemDetails form and validate/bind the actual sanitized classification/message, status and offending-field evidence, with provenance back to the correlated capture. Preserve HTTP400, Failed operation, resource/API/correlation linkage, no-commit confirmation and original prepared/update/proposal hashes. Distinguish any local classification label from an Azure-supplied code. Preserve null honestly in prepared/result evidence; update the packet. Add a representative no-code ProblemDetails success case and rejection cases for wrong status, fields, provenance and ambiguous/no-commit state. Do not modify the actual capture to manufacture a code.

### Major M2 — Validated configuration is compared without its two read-only exclusions

- **File/Module:** `scripts/quality/table_production_acceptance_continue.py:238–279`; validation-envelope contract in `packet.md:83–87`.
- **The Issue:** Lines269–277 compare envelope `properties.configuration` directly with live `app.properties.configuration`. The coordinator reports that the exact already validated `ffc9c3…` envelope intentionally omits only `configuration.ingress.fqdn` and `configuration.ingress.targetPortHttpScheme`; live metadata contains the read-only ingress fields. Python dictionary equality consequently rejects this truthful envelope even though the immutable template hash passes. The synthetic fixture copies the whole live configuration and does not exercise this difference.
- **Why Static Analysis Missed It:** Both operands are valid dictionaries; the incompatibility depends on the provider's writable validation representation versus GET metadata.
- **Impact:** Preparation cannot accept the actual successfully validated envelope. Rewriting that envelope would destroy its existing validation/hash provenance.
- **Recommended Fix:** Derive a comparison copy of live configuration and remove only `ingress.fqdn` and `ingress.targetPortHttpScheme` for this validation-envelope comparison, then require strict equality with the preserved envelope. Keep all other nested fields and existing strict comparisons intact; do not generalize to arbitrary missing/read-only fields or weaken live configuration/pin guards. Preserve the exact envelope bytes/hash and original template-only PATCH bytes. Test acceptance of precisely these two omissions and refusal for any other configuration removal/change, template drift or hash mismatch. Document the two explicit exclusions.

### Required evidence-reference clarification — No invented validation operation IDs

At lines289–290, `validation_id` and `what_if_id` are only required to be truthy; the code does not independently require service-generated or unique IDs. This is not a third demonstrated predicate blocker. However, the exact handoff must document each reference's kind and provenance. If Azure returned no unique operation ID, a real request target may be used only when explicitly identified as a request target, not a service-generated operation identifier. Bind the actual read-only response captures, request target and available Activity/request correlation to the validated envelope and operation outcome. A reusable target alone does not establish a unique successful invocation. Update the packet/schema description and bind any added capture hashes/kind metadata through prepared evidence; never synthesize an Azure identifier. The exact reviewer must inspect these actual sources before approving.

## Initially reviewed bytes (historical)

| Artifact | Independently computed SHA-256 |
| --- | --- |
| [Continuation runner](../../../../scripts/quality/table_production_acceptance_continue.py) | `b4417b262beefa80a85a7d2d4f5d596cbeb466e342e2794274c67ef8ddb3f973` |
| [Continuation tests](../../../../tests/unit/test_table_production_acceptance_continue.py) | `983acd371e9301d36efa11836d50f4dbc3db022684fe999d553a07fb9cea8345` |
| [Operational packet](packet.md) | `4f54b86323f14b6920c9e1b53eaca66b4fd5d4fd6854ed6a7195ea2a00963f0b` |
| Frozen original helper | `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922` |
| Frozen original tests | `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b` |
| Frozen recovery helper | `e3c47d6c7b7634c5578032df06795d4363205804f475d58d80f4560e7c8b6f45` |
| Frozen recovery tests | `762df8cb9e932ada219c1afe6b7b709c9e2dc4438cde732bcf6a5b041ef1f887` |

Read the plan inputs/activities/exit criteria/evidence, canonical operations and agent guidance, prior recovery exact review, runner/tests and relevant frozen implementations. Applied the repository contextual deep-review criteria to lifecycle, financial integrity, ownership, evidence and deadline boundaries.

## Other implementation boundaries and evidence intent

1. **Exact failed history and one new operation.** `history()` requires the exact original/recovery prepared hashes, original ledger/slot allocation, failed summaries, cold/drained/stop/absence/update linkage and strict directory inventories. Original four slots remain USD0.01792 aggregate within the existing USD1/16-attempt program. Existing case, restart, success or conflicting journal files refuse continuation. Neither old apply/history entrypoint is called.
2. **Confirmed rejection precedes preparation.** The intended contract binds correlated API2024 HTTP400/no-commit classification to recovery preparation, original consumed update and unchanged proposal bytes. M1/M2 source fixes are described above; actual captures remain subject to independent exact review. API2025 support, successful validation/what-if, the full `ffc9c3e051b9b0c8fe407773899c06ad3d3fdd719defa2d7f1c8f09a7c58948a` envelope and exactly one bound-app Modify/all other Ignore remain mandatory. The envelope must not be substituted for the template-only PATCH body.
3. **Stopped means stopped.** Discovery rechecks original old-image/Table/min0 configuration, production projection, secret pins, model/pricing/resource mapping and proposal. Strict all-revision enumeration requires every revision inactive and every worker absent. M3 supersedes the prior assumption that public403 is necessarily available in this state: a narrowly bound route-absent404 needs its own evidence and must not replace live-route403. No old-worker warming, activation or additional stop is authorized. Worker absence does not establish balances.
4. **Exclusive irreversible consumption.** Apply holds original execution/program, recovery execution and new continuation/execution locks. Fresh exact approval binds prepared history, source/evidence and ownership acknowledgements. Exclusive fsynced original/new consumption precedes the one API2025 template PATCH. A failed or ambiguous PATCH exits before successor acceptance or paid dispatch; there is no retry based on a later-appearing worker. Original consumed2024/history bytes remain intact.
5. **Financial gate before money.** The successor must be sole ready current-image Table/retry0/min1/max1 with preserved configuration/pins, effective environment and server command. Both current account maps must equal bound old-drained state. Legacy missing counters are interpreted only by the old baseline reader; current debit/recovery fields must be explicitly present. Account parsing requires zero reservations, valid balances and counters. Settings/proposal/source bindings preserve allowances and initial-setting inputs; no refill, repair or new Table allocation occurs.
6. **Four original slots with continuous settlement.** Before every original paid marker, process identity and the complete financial map must equal the last accepted state. Markers precede HTTP. Frozen dispatch persists numeric header/terminal observations and requires completed bounded usage and clean EOF. Configured-price debit must fit the original slot; balance/debit changes use the original tolerance, with other accounts, cycles and recovery unchanged. Ambiguity prevents later slots and retains liability.
7. **Actual staged persistence proof.** Final DENY403 and100-second drain require the same process, unchanged request counters and final finances. One targeted restart must produce changed actual container generation/restart metadata and changed process identity on the same approved revision, with readiness/effective environment and both persisted account maps intact. Results preserve original failure history and `original_apply_completed:false`, adding complete continuation provenance. Success stays test DENY/min1/max1; separate original-ingress/min0 cleanup and downstream result-chain validation remain outstanding.
8. **Bounded sequential helper reuse.** The capsule uses the frozen absolute public/worker/overall deadline helpers and synchronous alarm wrappers without introducing concurrent signal ownership or unbounded retry. Alarm state is restored in `finally`; nested Azure calls reuse the active budget. Native command failures remain redacted and fail closed. The prior claim that no evidence change was required is superseded by M1: the contract must represent the actual no-code ProblemDetails rejection. Any new unknown failure still requires a fresh decision.

## Independent local verification

Executed:

```bash
.venv/bin/python -m pytest -q -o addopts= -p no:cacheprovider \
  tests/unit/test_table_production_acceptance_continue.py \
  tests/unit/test_table_production_acceptance_recovery.py \
  tests/unit/test_table_production_acceptance.py
```

**173 passed**,15 dependency deprecation warnings,1.90seconds, before the compatibility findings were supplied. This includes the new continuation faults and frozen financial/dispatch/deadline tests. Test fixtures deliberately replace Azure and source-provenance discovery; these results do not prove actual source/image or live-state equality. In particular, they supply the invented error-code shape and unstripped configuration, so they do not clear M1/M2. The developer reports42 continuation tests/99.58% coverage; coverage was not independently measured in this review. The parallel full verifier owns full-suite, coverage, lint/format/type evidence. This documentation-only follow-up did not rerun unchanged tests.

## Historical C handoff (completed by the D review above)

Resolve M4 through the owning developer after the current source freeze/verifier handoff and obtain affected verification plus independent re-review of new hashes. Preserve the implemented M1/M2/M3 fixes and actual evidence references. Prepare a fresh private packet using complete revision enumeration; preserve C unchanged. Coordinator captures must retain actual correlated provider/Activity Log/validation/what-if facts, including absence of an error code or service-generated identifier, and actual stopped-state status. The exact C review refreshed live configuration/pins and all-revision worker metadata and checked sanitized capture binding; it did not reissue validation/what-if or independently requery the prior Activity Log event. Full runtime/build/image hash checks passed for C and must still pass for its successor.

The independent exact reviewer must inspect the resulting private prepared packet and actual captures, verify current stopped state and unused-slot/history/source bindings, accept completed verification, and confirm executor exit/production writer pause before issuing fresh approval. No private approval was created here. Production remains memory/one, and actual promotion, inference and restart remain unexecuted by this reviewer.

Only this review document was authored; source, tests, existing artifacts and unrelated working-tree edits were preserved.
