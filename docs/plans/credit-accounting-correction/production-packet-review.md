# Independent production packet review — October 29, 2026

**Current verdict: Approved for the exact revised packet below.** H1–H3 are resolved after independent re-review. Earlier findings are retained as review history. Runtime implementation and monetary-ceiling approvals remain valid; this review concerns the executable release procedure.

Reviewer: independent `credit_plan_review` / `gpt-6-astra` session. Reviewed [production packet](production-packet.md), private `/private/tmp/router-credit-handoff.py`, `/private/tmp/router-local-snapshot.py`, and prepared/before-app/before-snapshot/pricing/allowance JSON artifacts. Read-only inspection only; no Azure mutation, inference or source edits were performed.

Reviewed SHA-256 pins: main script `0e5005f8ddda3463371a1669930a6ce902163e801869c4f1ab7cfa544d3d8f49`; helper `6f0ccb0bcda3846d899504b1b30b6a8fa1d67039188eb20f9fc0b56e23eee1ab`; packet `0e53ad91a64ef7842be791f2c5e671730e0da69ef7c5aaa6930ea239c35e37b8`.

## Major H1 — Barrier and promoted-configuration invariants are not enforced across phases

- **File/Module:** `router-credit-handoff.py`, `fingerprint`/`guard_old`, `secrets`, `promote`, `allow`, `accept` and `restore` phases.
- **The Issue:** The configuration fingerprint deliberately excludes ingress restrictions. `secrets` and `promote` do not verify that the exact deny-all rule and externally observed denial still hold. They rely on an earlier stored `external_denied` boolean and quiet/current-equal credit snapshots. Quietness does not establish admission exclusion. After promotion, `allow`/`accept`/`restore` likewise do not consistently bind the whole expected promoted configuration, exact rule set and approved process before acting. For example, `accept` tests only the first rule's name, not action/CIDR/count; `restore` can reopen a drifted configuration before detecting it.
- **Why Static Analysis Missed It:** Each local assertion is valid, but the exclusion guarantee must remain true across separate executions and mutable cloud state.
- **Impact:** An operator recovery or concurrent configuration edit could reopen ingress after the initial drain, then pass a quiet observation. The procedure may deactivate/promote with open ingress and stale seeds, or restore public intake for an unverified configuration.
- **Recommended Fix:** Add phase-specific guards that bind complete expected pre/post application configuration, exact rule arrays, source process/revision identity and current external denial/access. Immediately before secret creation and especially old-writer deactivation, re-prove the exact deny barrier and fresh unchanged drained state. For allow/accept/restore, validate the full promoted configuration and exact expected access rule before mutation or inference. Recheck resulting state afterward. Preserve stop-on-drift behavior rather than restoring arbitrary current state.

## Major H2 — Executed helper and state/secret bundle are not bound through the final handoff

- **File/Module:** `router-credit-handoff.py:53–56,86–89,154–172,186–215`; snapshot helper; prepared/drained/secret-pins artifacts.
- **The Issue:** The snapshot helper is executed without a checked hash, as the packet itself acknowledges. The main guard checks source/script files but not all immutable prepared evidence or phase artifacts. `drained.snapshot_sha256` is written but not checked on use. The promotion phase trusts the current `secret-pins`, `initial`, `pricing` and `allowance` files without rechecking their approved hashes or rereading all pinned secret values; its post-promotion checks compare against those same mutable local files. This does not implement the packet claim that prepared monetary values are hashed before every phase.
- **Why Static Analysis Missed It:** These artifacts form an operational chain of evidence outside the application type system; write/read operations individually succeed even if the wrong snapshot or secret version is substituted.
- **Impact:** An accidental artifact edit, stale capture or changed secret-pin file can change the seed/configuration accepted at promotion. An unreviewed snapshot helper can change what qualifies as a drained, unchanged writer.
- **Recommended Fix:** Bind and verify the helper before every execution; verify the prepared baseline snapshots and derived drained snapshot/initial hashes on every dependent use. Persist a hash of the exact secret-pin bundle and, immediately before deactivation, reread every pinned secret and compare it with its reviewed/prepared monetary digest. Bind promoted/allowed/acceptance evidence to expected configuration, process and unique execution identity. Independently review refreshed hashes before execution.

## Major H3 — Acceptance spend bound omits router retries and failover

- **File/Module:** production packet acceptance step; `router-credit-handoff.py:240–277`; existing `forwarding/__init__.py` retry loops and `routing/__init__.py` failover.
- **The Issue:** The packet says no retries and computes the pair bound as two provider attempts. The literal client has no retry loop, but the preserved production setting is `FOUNDRY_RETRY_ATTEMPTS=2`, and the two-backend pool permits failover to the second backend. There can be up to four upstream attempts per public call. A timeout or another retryable failure can occur after billable provider work.
- **Why Static Analysis Missed It:** The budget calculation is external to the forwarding/failover behavior and confuses public acceptance slots with provider dispatches.
- **Impact:** Two calls at 128 input/128 output and prices 5/15 USD per million can reach an upper local estimate of 2 × 4 × USD0.00256 = USD0.02048, above the stated USD0.01 budget. Abort-after-result and a consumed public slot do not stop retries already performed inside the router.
- **Recommended Fix:** State separately that public slots are never replayed and internal retries/failover retain their existing bounds. Either revise the reviewed allowance to cover all possible upstream attempts, reduce the literal request bounds so the full maximum fits, or use a separately reviewed mechanism enforcing one provider attempt. Bind and validate the exact request body/estimate and worst-case attempt budget before the first dispatch. Preserve no-retry-after-meaningful-SSE-output behavior.

## Verified and acceptable parts

- Prepared allowance and six pricing triples match the independently approved monetary amendment; other account allowance values are preserved.
- The drain uses replica-local authenticated diagnostics without printing the admin key, compares revision/replica/PID1 start ticks, waits for reservations, and subtracts inflight amounts before flooring inherited seeds. The private helper keeps provider bodies out of stored diagnostics.
- The code deactivates the old revision and requires successful empty active-revision and old-replica listings before its promotion PUT. It records a promotion marker before PUT and consumes acceptance slots before dispatch, avoiding ordinary automatic replay.
- Response ingestion has time/size limits; terminal completion and usage integers are checked; expected settlement is compared against canonical account counters with recovery unchanged. The packet correctly avoids claiming nonzero-cache acceptance if the observed cached count is zero.
- The immutable image digest is specified and sources are frozen. Source, runtime and monetary acceptance remain distinct from this executable handoff review.

## Re-review requirements

Resolve H1–H3, update executable/helper/artifact bindings and the packet, then obtain independent re-review before mutation. Add focused local tests or mocked phase rehearsals demonstrating refusal on barrier drift, helper/seed/pin changes and promoted-config drift; verify the corrected attempt-budget arithmetic. The described optional vault grant also needs its exact operator/scope/role and ownership-only cleanup record in the concrete execution evidence before use. No stale-seed rollback or replay of ambiguous acceptance is authorized by this review.

## Re-review of guarded packet

**Verdict: Changes required — residual Major H1 only.** Independently reviewed main script `975e798995ff4ae1f14d31dbeccd1f7b6b7fa2b8a99362f80e412af1061e8a60`, unchanged helper, rebound prepared artifacts and packet `d3b424c2c817edf9df658236f65f3751606598353c8fe37e6d41d7127d97743b`. Independently executed private mocked guard rehearsal `fbdfc005d1fea88a175f0e3e4dd9b468b2bd926fcee196a34d2b8b56f9c2fb6a`: seven drift refusals passed; USD0.02048 worst-case arithmetic passed within USD0.021. No Azure mutation/inference performed. SonarQube script remains absent, not a successful scan.

H2 is resolved by checked helper/baseline hashes, drained snapshot/seed seals, pin-bundle seal and reread of pinned values before deactivation. H3 is resolved by accounting for four upstream attempts per public call and explicitly prohibiting public replay. H1's pre-deactivation and later allow/accept/restore guards are substantially resolved.

- **Severity:** Major (residual H1).
- **File/Module:** private `router-credit-handoff.py:214–215,233–252`.
- **The Issue:** After waiting for old writers to disappear, promotion verifies only a fingerprint that excludes ingress, and clones the current rules into the deployment body. After deployment it checks only the first rule's action and seals the observed configuration without comparing its full fingerprint to the intended body.
- **Why Static Analysis Missed It:** This is a cross-phase mutable-cloud-state invariant, not a local type or syntax error.
- **Impact:** Ingress drift during shutdown can be carried into the new revision, and unrelated post-PUT configuration drift can become the accepted baseline used by later guards.
- **Recommended Fix:** Require exact `DENY` rules on the post-shutdown resource immediately before constructing the PUT; require exact `DENY` and `fingerprint(new) == fingerprint(b)` before capturing the promoted seal. Unexpected platform normalization should stop execution for review, not silently weaken comparison.

Suggestion: remove obsolete optional role-grant language from the packet now that existing vault-scoped access is verified. No additional role assignment is covered by this review.


## Final independent re-review — Approved

Reviewed final private script SHA-256 `081dc6e55bed3b5d3ab590890586061e1501bf07eb3e3a2ac7285a2cde25c230`, packet `6220311eec3d5d60d9ecaa6989c1a717da4a365cc445eac750953af29aa9171a`, and rebound prepared JSON `b8f5a62557b2d2022b1bb1230c0886d641e1a7f800764c645a5e813e2adf35c9`. Helper remains `6f0ccb0bcda3846d899504b1b30b6a8fa1d67039188eb20f9fc0b56e23eee1ab`. This is the independent `credit_plan_review` / `gpt-6-astra` session; reviewer authored neither executable nor implementation.

Residual H1 is resolved: line 214 requires exact deny rules after old-writer exclusion, and line 233 requires exact deny rules plus intended-body fingerprint equality before promotion evidence can be sealed. H2 and H3 remain resolved. The optional role-grant suggestion is addressed by removing it; this execution uses existing permissions. No unresolved Critical or Major findings remain in the reviewed packet.

Independently reran the seven mocked drift-refusal checks against the final script, all passed. The rehearsal also checks current prepared/helper/baseline/source hashes on its successful path and verifies USD0.02048 is within the USD0.021 acceptance budget. These checks are local evidence, not proof of live Azure behavior.

Approval covers only the bound prepared execution, immutable image, three monetary secret versions, guarded memory/one-replica handoff, two consumed-before-dispatch public acceptance slots and restoration after both pass. It does not cover new role grants, Table cut-over, historical refunds, replay of ambiguous inference, stale-ledger rollback, or weakening a failed guard. A new preparation or material executable/configuration amendment needs fresh review.

Remaining execution gates: current exact deny/public-status proof; unchanged drained process and monetary snapshots; pinned-secret readback; old writers absent; intended sole healthy revision and loaded settings; both bounded usage/debit acceptance cases; unchanged process and exact final ingress/configuration restoration. Production mutation and acceptance remain pending; no deployment or live success is claimed by this review. Absent SonarQube script remains not applicable, with prior runtime verification evidence documented separately.
