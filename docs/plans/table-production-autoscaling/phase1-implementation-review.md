# G1 independent contextual implementation review

Date: 2026-10-30. Reviewer: independent GPT 6 Astra session, not the harness author.

The initial review below is preserved as historical evidence. Its two Major findings are **resolved** by the appended [current re-review verdict](#current-re-review-verdict--2026-10-30).

Latest outcome: **all IR/EP Major findings are resolved**. The final EP-M2 closure and exact `e`-packet approval are appended below and recorded in [the exact-packet review](phase1-exact-packet-review.md).

## Verdict

**Critical: 0. Major: 2 unresolved. Suggestions: 3.**

Read-only preparation/discovery may proceed. **The current script is not ready for exact execution approval:** resolve the two Major findings, then generate and independently review the final prepared packet against the corrected helper/test hashes. This review approves no Azure mutation, paid call, restart or production transition. No actual prepared packet was supplied or approved here.

The original plan's **M1 mixed-version-writer sequencing is addressed at implementation level**: fence and drain the old process, deactivate its revision, enumerate all revisions/replicas until workers and active revisions are absent, then update and require a sole ready successor with unchanged financial state. Exact identities, historical-row compatibility, effective single-worker configuration and actual transition evidence remain packet/execution gates. The new findings below have distinct IDs.

Successful execution may be accepted as **staged G1 acceptance, fenced at min1/max1**, if the exact reviewer explicitly accepts that disposition. It is not completed restoration or task cleanup. A separate reviewed transition must later restore the captured original ingress/minimum and verify the resulting worker/state. Production's four accounts remain outside this isolated acceptance.

## Review basis and limits

- Read all 1,125 harness lines, all 845 focused-test lines, the phase-one packet, original independent plan review, relevant plan/evidence, canonical operational guidance, Docker entrypoint and owning runtime accounting/forwarding/admin boundaries. Followed the contextual scope and finding format in [the deep-review prompt](../../../.agents/prompts/deep-review.prompt.md).
- Inspected `git status`; pre-existing source/docs/test changes are user work. Only this review file was authored. No Azure commands, network/paid requests, source edits, deployment, builds or verification-suite reruns occurred. A local `python -B` in-memory predicate check exercised the financial gap below without writing artifacts.
- Sonar scan script is absent: **N/A, not passed**. The independent verifier owns concurrent verification. Baseline 2,887 tests/90.46%, 15 Azurite passes, 78 pinned source/build inputs and 76 matching in-image Python files are supplied coordinator evidence. Developer 56 tests/95.19% harness coverage is a reported result, not this review's rerun.
- Supplied discovery identifies the selected test deployments with the dedicated `af-opencode-agents` Foundry resource, distinct from production resources/hosts. The old synthetic USD 100 is only a debit-delta baseline; the fresh USD 1 authorization is outside production funds. Actual resource IDs and liability evidence must be bound privately during exact review.

Reviewed SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `scripts/quality/table_production_acceptance.py` | `5d7bf365f3a97eedc1bdb8da6f7ec86b5fe35c6bf5c39bcf408384cffff0bac7` |
| `tests/unit/test_table_production_acceptance.py` | `84585e098a793c8dc51bdc8697bc33d96a3763945f90de81b6867b44945c0a91` |
| `docs/plans/table-production-autoscaling/phase1-packet.md` | `92c1582437041303a6b071d5019fd2529a616dbb95f32e21e47338fcf8fa73b3` |

## Major

### IR-M1 — Financial continuity is not checked between paid cases

- **File/Module:** `scripts/quality/table_production_acceptance.py:993–1045`, especially the new `before` snapshot at 1012 and pairwise comparison at 1041; orchestration tests at `tests/unit/test_table_production_acceptance.py:660–707`.
- **The Issue:** Each case accepts its own fresh financial baseline without comparing it to the successor baseline or the previous case's accepted `after` state. An extra debit, replenishment, recovery, membership change or cycle rollover between those snapshots becomes the next accepted baseline. Process/environment checks do not establish financial continuity. The final drain/restart only preserves the last case's state.
- **Why Static Analysis Missed It:** Every individual debit comparison is valid. The missing invariant spans successive operational snapshots and the run's original financial baseline.
- **Impact:** All four cases and restart can be reported passed despite unexplained financial drift or unreserved external consumption during acceptance. This invalidates the isolated accounting/no-unexplained-drift evidence, even though it does not mutate production.
- **Recommended Fix:** Carry the last accepted account map, initially `accounts(baseline['admin'])`. Before consuming every slot, require `unchanged(last_accounts, accounts(before['admin']))`; after successful debit verification, advance it to the accepted `after` map. Preserve the existing final drain/restart comparison. Add focused orchestration cases injecting drift after baseline/between cases, including another group's change and a cycle change; assert refusal before the next slot/dispatch. No runtime changes are needed.

**Local evidence:** An in-memory check started at USD 100, accepted a USD 0.01 call, inserted an unexplained USD 0.25 debit between snapshots, and accepted another USD 0.01 call. Both existing `verify_debit` calls and final `unchanged` persistence check passed. This exercises the actual predicates; it is not a live or full-orchestration run.

### IR-M2 — Public diagnostics have inactivity timeouts, not total deadlines

- **File/Module:** `scripts/quality/table_production_acceptance.py:431–440`; callers during prepare and after ingress mutations at 778–783, 940–942, 1006–1009 and 1047–1050.
- **The Issue:** `httpx.Client(timeout=10)` bounds individual network waits. `iter_bytes()` has no enclosing wall-clock deadline. A response delivering occasional bytes faster than that timeout can keep the process waiting far beyond the intended operational bound, until the 4 MiB cap is eventually reached. Paid `dispatch_async` correctly uses `asyncio.timeout(TIMEOUT)`; the diagnostic path does not.
- **Why Static Analysis Missed It:** A timeout and capacity check both exist, but neither makes the complete streamed GET time-bounded. This depends on HTTPX's timeout semantics and where the helper is called in the mutation sequence.
- **Impact:** Prepare can stall; apply can stall after consuming the run and changing ingress, holding its lock and leaving the task in a partially transitioned state rather than reaching the documented bounded stop/recovery outcome.
- **Recommended Fix:** Give the complete GET/status/body operation an absolute deadline, preferably the same small async-wrapper pattern already used for dispatch. Retain the byte cap, redirect/proxy restrictions and sanitized failure handling. Add a no-network slow/trickling stream test that proves expiration despite continued bytes; retain a normal-response case. Do not add retries or recovery mutations.

## Suggestions

### IR-S1 — Correct the restoration artifact pointer

- **File/Module:** `docs/plans/table-production-autoscaling/phase1-packet.md:96–100`; harness `results.json` at 1071–1078.
- **The Issue:** The document says `results.json` records the exact original ingress and original minimum. Only the minimum is included there; the exact original ingress is in `prepared.json`.
- **Why Static Analysis Missed It:** This is a prose/artifact contract discrepancy.
- **Impact:** Cleanup operators could look in the wrong artifact or mistake staged success for a complete restoration record.
- **Recommended Fix:** Point explicitly to `prepared.json.original_ingress` and `prepared.json.original_min`; retain `results.json` as the staged outcome. Existing explicit restoration-pending status is appropriate. No automatic rollback extension is required.

### IR-S2 — Confirm resource identity disjointness in the exact packet

- **File/Module:** `scripts/quality/table_production_acceptance.py:398–421`; exact prepared resource review.
- **The Issue:** The executable compares test hosts against production hosts and resolves test hosts to management resource IDs. Different endpoint aliases can identify the same Cognitive Services account, so host disjointness alone is not a general proof of resource disjointness.
- **Why Static Analysis Missed It:** Azure account endpoint aliases and allocation ownership are external facts.
- **Impact:** Reusing this harness with different inputs could mislabel a shared resource as dedicated. The supplied current discovery explicitly identifies distinct resources, so this is not an additional blocker for this known target.
- **Recommended Fix:** In the required exact review, confirm the selected management resource ID is distinct from every production inference resource, rather than approving only unequal DNS names. Keep that evidence private and retain the honest zero-production-account-coverage statement. General-purpose resource-mapping expansion is unnecessary for this packet if the reviewer verifies the concrete identities.

### IR-S3 — Exercise the existing stream deadline and restart rejection paths

- **File/Module:** `tests/unit/test_table_production_acceptance.py:378–441, 601–615, 736–753, 801–845`.
- **The Issue:** The successful orchestration mock bypasses actual replacement polling; dispatch tests cover clean completion and a transport timeout, but do not exercise terminal-completed-then-stalled EOF or fragmented failure paths. The zero-second polling test proves immediate deadline rejection, not rejection of an unchanged ready container over a polling interval.
- **Why Static Analysis Missed It:** High line coverage does not establish the operational meaning of completion and replacement evidence.
- **Impact:** Future changes could weaken single-shot terminal/EOF handling or accept a no-op restart while the happy-path mocks continue passing. No additional implementation defect is asserted here.
- **Recommended Fix:** Prefer a few bounded no-network tests: completed SSE followed by a stalled stream retains terminal evidence but produces no success; unchanged actual container identity/count and unchanged process cannot pass restart; failed/incomplete terminal status prevents subsequent calls. Keep the 128-output bound and stop rule unchanged.

## Accepted implementation choices and remaining exact review

- Source/image binding includes runtime-file set equality, immutable image, prior metadata, helper and test hashes. Pre-mutation projections bind app configuration/resources; successor projection permits only reviewed image, retry and minimum changes (plus revision naming). Credentials are resolved from version-pinned Key Vault references and hashed; exec arguments contain code rather than keys. Snapshots persist selected diagnostics and numeric usage, not prompts/model output.
- Owner-only external artifacts, exclusive creation/fsync, execution locking, whole-run/slot consumption before operations, and retained ambiguity provide appropriate single-use behavior. This G1 executable makes at most four sequential calls; the 16-attempt figure is the larger program envelope, not permission to rerun G1 with fresh paths. Later phases must account for the existing reservation ledger.
- Current source owns estimation/settlement. The minimal fixed prompt, 64-input reserve and 128-output limit are reasonable bounded acceptance choices with the supplied synthetic pricing/liability distinction. A reasoning model may exhaust its output budget and return incomplete; stopping without a retry, substitution or increased limit is correct. Provider compatibility remains a live acceptance question, not grounds to weaken the stop rule.
- The paid HTTP/SSE path has an absolute timeout, bounded bytes, terminal status/usage checks and early durable HTTP/terminal evidence. It requires clean EOF and never dispatches another case after an exception. Unknown outcomes retain consumed liability.
- Actual restart requires metadata generation change followed by changed process identity and unchanged persisted financial state. Single replica is not by itself proof of single worker: the exact reviewer must also inspect effective launch/environment settings, including any non-`FOUNDRY_` worker controls, against the verified Docker entrypoint.
- After IR-M1/IR-M2 fixes and independent verification, bind a fresh packet. Review concrete resources/configuration/rows, original ingress/minimum, available permissions, budget disposition and staged restoration acceptance before granting any execution approval. This document is not that approval.

## Current re-review verdict — 2026-10-30

**Unresolved Critical: 0. Unresolved Major: 0. IR-M1 and IR-M2 resolved. Ready for read-only prepare and subsequent independent exact-packet review. This is not execution approval.**

This verdict supersedes the initial implementation verdict for the hashes below. No actual prepared packet has been reviewed here. The original plan's M1 writer-stop sequence remains addressed in code; live old-writer absence, successor behavior and restart persistence remain execution evidence to collect only after exact approval.

### Current reviewed bindings and evidence

| File | SHA-256 |
| --- | --- |
| `scripts/quality/table_production_acceptance.py` | `b0a30682941ed46e368fbd59b0148bb80c9634a91272da363bc17e122d4089b2` |
| `tests/unit/test_table_production_acceptance.py` | `3ec4dbff84f0cfd41c4b6bf871cec813f3b881310c936bd0bf20c44f816f011b` |
| `docs/plans/table-production-autoscaling/phase1-packet.md` | `fbc4f8230e0f4218ffe36f6f3dd475b9d6d4008ae09e08cd02ce90ae84060501` |

Read the corrected 1,160-line harness, 1,159-line test file and 200-line packet. All three locally calculated hashes match the supplied prefixes. Developer **83 passed / 96.93%** coverage remains a reported result; the existing independent verification document still records the earlier 56-test revision at this review time. Do not attach that older verification result to the new hashes as a fresh rerun. Sonar remains N/A.

Independently invoked five existing no-file tests directly using `python -B`, `pytest.MonkeyPatch`, mock HTTP and in-memory stdout capture: normal public GET, trickling GET total timeout/no retry, unchanged ready-container rejection over multiple polls, native-error redaction, and actionable literal refusal reporting. **All five passed.** This is targeted review evidence, not an 83-test/coverage rerun. A source-AST check also confirmed all 108 refusal reasons are literal strings; the sole indirection is `require` forwarding its literal caller message. No Azure commands, network calls, source edits or test artifacts were produced. Only this review document was changed.

### Finding closure

- **IR-M1 — Resolved.** Harness lines 1032–1038 initialize `last_accounts` from the accepted successor baseline and require exact equality with each case's fresh account map **before** slot consumption or HTTP. Lines 1065–1067 advance the chain only after valid debit reconciliation. Final drain compares against that same accepted map at 1080; restart preserves it at 1093. Whole-map equality catches membership, cycles, recovery and other-group changes as well as balance/counter drift. The 16 new orchestration cases at test lines 849–904 inject eight kinds of drift before case zero and between cases, checking that the next slot and dispatch remain unconsumed. The historical counterexample can no longer cross this boundary.
- **IR-M2 — Resolved.** `get_public_async` at lines 435–448 encloses client creation, streamed GET headers and the complete body in `asyncio.timeout(TIMEOUT)`. It retains a 4 MiB capacity bound and disables ambient proxies and redirects. The 60-second inactivity setting cannot extend the separate absolute deadline. The existing wrapper remains synchronous for callers; timeout exceptions reach sanitized stop handling because `TimeoutError` is an `OSError`. The normal and trickling mock tests passed independently, with the latter confirming one request despite continued bytes.
- **IR-S1 — Resolved.** Packet lines 108–116 correctly point to `prepared.json.original_ingress` and `.original_min`, identify `results.json` as staged outcome evidence, and retain separate restoration approval.
- **IR-S3 — Resolved.** Added tests cover completed-but-stalled SSE retaining terminal evidence without success, fragmented failed SSE retaining consumption, unchanged ready-container rejection across a polling interval, unchanged process after a no-op restart, and incomplete response stopping later slots. The unchanged-container test passed independently; the remaining new cases were inspected and belong to the reported focused suite.
- **IR-S2 — Retained as an exact-review requirement, not an implementation blocker.** Packet lines 199–200 now expressly require concrete management-resource identity disjointness including aliases. The supplied dedicated-resource discovery remains consistent with this requirement. Exact private IDs, current production resources and separate liability must still be reviewed in the actual packet.

### Cold-start preparation and redaction

The new prepare path at lines 784–804 is acceptable for the known min0 isolated app: one unauthenticated public readiness GET, HTTP 200 plus object-shaped `ready: true`, bounded ready-writer polling, refreshed app metadata, then exact replica exec and the existing effective-environment/account/auth checks. It introduces no inference, CLI configuration mutation, ingress change, retry or paid-slot consumption. Readiness intake can wake the existing replica; this is not a claim that the runtime stays asleep. Failed warming/waiting occurs before packet creation and before any reservation/consumption artifacts. The cold/empty-to-ready and timeout tests explicitly cover those outcomes.

The new error output at lines 1135–1151 emits exception type and a developer-authored literal `RefusalError` reason; ordinary Pydantic/HTTP/OS/CLI exception details remain withheld. No untrusted response/secret content is interpolated into current refusal reasons. Warm-response contents are parsed for readiness and not persisted or printed. Existing secret hashes, credential-free exec arguments and numeric-only usage artifacts remain intact. The two independently invoked reporting tests passed.

### Nonblocking timing clarification

- **Severity:** Suggestion.
- **File/Module:** Packet line 18 and `wait_writers` at harness lines 630–643.
- **The Issue:** “Waits at most 60 seconds” describes the polling window, not a strict total deadline around the nested Azure CLI calls. A poll begun before expiry can finish after it; each CLI call has its own 60-second timeout.
- **Why Static Analysis Missed It:** The distinction depends on nested operational deadline semantics.
- **Impact:** The worker-discovery step can take longer than the prose suggests. This does not reopen IR-M2: public HTTP has a genuine total deadline, and CLI calls remain individually bounded with fail-closed handling.
- **Recommended Fix:** Describe this as a “60-second polling window with individually bounded Azure CLI calls.” A broader subprocess-deadline redesign is not required for read-only preparation or this packet's implementation approval.

### Handoff boundary

Proceed with fresh read-only prepare and independent verification/exact review of the resulting private packet. Preserve original artifacts and bind the corrected hashes. Review the effective single-worker launch, live settings/rows, dedicated resource IDs, budget and staged restoration disposition before any execution approval. Successful G1 still ends fenced at min1/max1; exact original ingress/min0 restoration and task cleanup remain a separate reviewed task. Production remains memory/one and its four accounts are outside G1 acceptance.

## Compressed transport and exact-review follow-up — 2026-10-30

Reviewed frozen harness `35e082c537bc144a59f3ad321175deec31ef0770360ccc856e1f44bc04c97e30`, tests `affa20a3e2d0dbfbfb5dd7fc2cf9d0bef714f7c88bd5d680877ffbd29af3d50a`, and packet document `8143d2da28a55943e839cb2207c428db2ed073a39ed09af25d51bf69433c02bf`. Compression directly wraps the existing snapshot program with zlib level 9 and base64; the command is 1,135 characters and decodes to the exact program bytes. Snapshot-program SHA-256 is `6f4c0dbce56e78b5611c687ab1f5121c9e7cf28976b05a262190046fce1e10e2`. No credentials enter command arguments, no console logging/retry was added, and the targeted snapshot/unique-result checks remain intact. Independently invoked the updated mocked PTY test with `python -B`: **passed**, without Azure exec or artifact writes. The compression change introduces no contextual finding; earlier IR-M1/IR-M2 closures remain valid.

**Current exact-execution status: blocked by one newly identified Major, EP-M1.** At the coordinator's request, examined deactivation transition semantics and reproduced immediate refusal when an inactive revision still has a draining replica. `wait_writers(absent=True)` cannot currently wait through that legitimate state because `Azure.writers` enforces the active-writer invariant first. The code still prevents overlap, but can strand the single-use run after deactivation rather than perform its intended bounded absence check. See the full finding and private-packet binding in [the exact-packet review](phase1-exact-packet-review.md). This refines the original M1 closure: the ordering/no-overlap requirement is implemented, but its transition observation needs a small correction before execution.

The exact review independently confirmed live projections/pinned secret hashes, one matching prepared writer, the Docker process command, and dedicated test resource-ID disjointness from every production Azure resource across accessible subscriptions. IR-S2's concrete resource-identity check is therefore satisfied for this packet. No source changes, Azure mutations, inference, prepare/apply or approval-file creation occurred. Fresh final verifier evidence and an independently reviewed corrected binding are still required; earlier verification cannot approve a changed executable.

## EP-M1 closure and update-path follow-up — 2026-10-30

Reviewed the complete limited diff for frozen harness `c56e8ce97cde14a48011dc24384c5cab0500851216012a3b1c96d8cf446cb20d`, tests `2565ab3684e97adc612c97a96d909db5cfd4befa89b7529ce16ba251102d7116`, and packet document `be271e4aa59ddf548b16139b0257c8eb403cc2ac3f89edbe937ed0648cd996f0`.

**EP-M1 is resolved.** Only deliberate absence polling enables `allow_draining`; it requires every revision explicitly inactive, counts all replicas across all revisions, and returns only at zero workers. The independent no-active check before update remains. Normal snapshot/readiness and replacement paths retain strict inactive-worker/overlap rejection. Independently invoked the new all-revision draining-to-absent and strict-readiness/replacement regression tests with mocks: both passed. Inspected the two orchestration regressions that prohibit update/slot consumption on persistent drainage or an unexpected active revision. The polling-duration prose suggestion is also resolved.

Final supplied verifier logs were available and inspected: **87 focused tests / 96.95% harness coverage; 2,974 passed, 21 skipped / 90.46% source coverage; Ruff lint/format and source/harness mypy passed.** These are observed verifier artifacts, not reviewer suite reruns.

**One new Major remains, EP-M2: the installed Azure CLI update path injects empty values into secretRef-only environment entries before sending its PATCH.** This repeats the historical isolated-update normalization problem. Confirmed directly in installed Azure CLI 2.91.0 source and with an in-memory successor-binding check on the eight bound secretRef-only entries. It is not merely a response-format concern. See the appended `d`-packet assessment in [the exact review](phase1-exact-packet-review.md). Use a narrowly scoped direct template PATCH preserving the bound environment shape; keep strict successor drift/credential checks. No source edit, mutation, inference or approval-file creation was performed by this reviewer.

## Final EP-M2 closure — 2026-10-30

**Unresolved Critical: 0. Unresolved Major: 0. EP-M2 resolved; all earlier Major closures remain valid.** Reviewed frozen harness `701cca098ce005703cc97d298adde7c7072e61ce8bf233b0f941c815ffa7e922`, tests `04b79e5fea57bb527dbf4015d401aff59697069dfa3c7fc2aee66851585e2a8b`, and packet document `59d486b5a459260f2a6f0e82e5a0f2cb084f97f47096481a677915ecfc1f4d5c`.

The replacement deep-copies the raw bound template, preserves secretRef-only records and unrelated resources/rules, applies the already-reviewed image/retry/minimum changes, and omits the old revision suffix. A pure validator reuses strict successor checks and refuses any body scope beyond `properties.template`. Prepare binds its semantic hash. Apply checks that hash before consumption, exclusively persists the private proposal and file binding, then rechecks original template/proposal bytes after old-worker absence and before the update marker. One `az rest` PATCH uses the private `@file`; the high-level CLI update/normalizer is gone. Existing post-update environment/secret/financial checks remain intact.

Independently invoked **nine no-file checks**, all passed: exact proposal/input preservation, six unreviewed-drift rejections, all-revision draining-to-absence, and strict readiness/replacement guards. Also reconstructed the actual `e` proposal from live read-only metadata: semantic hash matched and all eight secretRef-only entries remained unchanged without `value`. Fresh final verifier logs record **95 focused tests / 97.10% harness coverage; 2,982 passed, 21 skipped / 90.46% source coverage**, with Ruff lint/format and both mypy checks passed. No Azure mutation or inference was used for review.

The exact `e` packet is approved as recorded in the exact review, including separate dedicated-resource liability and staged test deny-all/min1 completion with later restoration. This closes implementation review; it is not evidence that live G1 or production migration has executed or passed.
