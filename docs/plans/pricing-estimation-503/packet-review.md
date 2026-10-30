# Production handoff packet review

Final verdict: **Approved for the exact prepared execution described in [production-packet.md](production-packet.md).** Final independent re-review, 2026-10-29 local date. No unresolved Critical or Major findings. This approves one invocation of `apply` through the prepared script's guards, not replay, refresh after approval, changed code/configuration, or recovery mutations.

Approved executable SHA-256: `4f3017206f3be8060ad288a2501ab0628eb90d90e2e5f3c3871546031d6909c8`. Approved dedicated helper SHA-256: `88349d8287ebef603bf2f982a8e1bca299e8162b27d27ec9c067c75a01858f07`. Immutable image digest: `36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4`. Source aggregate: `ff0d1a74c3bb226b7faa13f6e3457580718aa28ab4a2d4c10f92509989eaed4d`. Baseline app/snapshot/secret-binding hashes are exactly those in the linked packet.

Reviewer directly verified local prepared artifact hashes, all configured loaded-environment hashes against literals/pinned secret values, complete app identity, current source-file hashes, all 16 existing secret URLs already matching their resolved versions, and absence of a consumed execution marker. Reviewed final script/helper: snapshot subscription and resource binding resolve the Major finding; actual transmitted byte measurement resolves the suggestion. Pinned apply-time values, worker-override rejection, command-hash continuity, exclusive execution lock, fresh-seed checks and unchanged-environment checks resolve the remaining packet requirements. No plaintext credentials were displayed. The ACR log confirms successful run `cab` with the approved digest; full-suite log confirms 2,884 passed and 90.45% coverage, and Azurite log confirms 15 passed. Coordinator reports four mocked drift-refusal checks; these were not independently rerun.

Remaining gates are execution outcomes: runtime admission closure/drain and writer exclusion, promotion/readiness, one no-egress rejection acceptance, same-process credit verification, and exact ingress restoration. Any guard failure or ambiguous mutation requires the packet's stop/read-only-reconcile/separately-reviewed-recovery procedure. No Azure commands or mutations were executed by this reviewer, and approval does not claim live handoff success.

## Historical review record (superseded by final verdict above)

Initial verdict: **Changes required; not approved for production execution.** Preliminary structural review only, 2026-10-29. Image and prepared baseline pins were pending.

Reviewed private `/private/tmp/router-pricing-503-handoff.py` (SHA-256 `c04c8905e1e507bb2df154f0729d7b487ab98c4c3eb39e105cf3f0561a5337c0`) and its snapshot helper `/private/tmp/router-local-snapshot.py` (SHA-256 `6f0ccb0bcda3846d899504b1b30b6a8fa1d67039188eb20f9fc0b56e23eee1ab`). Reviewed relevant intake deadline and reservation lifecycle code and Docker entrypoint. Private resource identifiers and credentials are intentionally omitted from this report.

## Findings

### Major — Snapshot authority is not subscription-pinned

- **File/Module:** `/private/tmp/router-local-snapshot.py:24-30` and handoff `snapshot()`.
- **The Issue:** Mutation/readback commands in the handoff pin the subscription, but all helper CLI commands inherit the mutable CLI subscription context. Helper results carry revision/replica names, not verified resource authority.
- **Why Static Analysis Missed It:** Correctness depends on consistency across independent operational processes and external CLI state.
- **Impact:** Handoff accounting evidence can fail or be gathered from a different same-named app, undermining the explicit authority boundary for the final seed snapshot.
- **Recommended Fix:** Pin the same subscription on every helper command and return/verify the full app resource identity. Rehash the helper/script and regenerate prepared pins before execution.

### Suggestion — Record actual transmitted request bytes

- **File/Module:** `/private/tmp/router-pricing-503-handoff.py:163-165`.
- **The Issue:** Acceptance sends HTTPX `json=`, but records length using default `json.dumps`, which inserts spaces. The reported count is not the actual transmitted count.
- **Why Static Analysis Missed It:** Both serializations are valid JSON; evidence accuracy requires comparing their wire conventions.
- **Impact:** The acceptance report misstates request size, although both bodies exceed the old bound and remain below intake.
- **Recommended Fix:** Serialize once and send those bytes, or measure `response.request.content`.

## Required packet completion

- Bind immutable ACR image digest to reviewed build/source provenance; replace placeholder image and populate baseline, script/helper/source hashes. Re-review exact completed hashes.
- Verify one worker as well as memory/max-one-replica: inspect effective command/args and worker-related environment against the pinned image entrypoint. Existing invariant checks alone do not assert worker count.
- Resolve every existing secret/config reference sufficiently to establish that unchanged references preserve the reviewed effective configuration at restart. A resource fingerprint of an unversioned secret URL alone does not pin its contents.
- Record operator authority and exact current baseline/exclusions. This reviewer has only coordinator-supplied authority context.
- Require single executor. The `started.json` check followed by replace is a replay guard for sequential retries, not an atomic lock against concurrent executors; use exclusive creation if concurrent invocation cannot be excluded.
- Record failure handling: an ambiguous mutation consumes this execution identity and requires fresh read-only reconciliation plus a separately reviewed recovery packet. Do not reset markers or replay apply; do not automatically reactivate stale memory state. A failure can intentionally leave ingress restricted/service stopped pending that recovery.

## Safeguards found

Interim re-review: revised script now uses a dedicated subscription-pinned helper, immutable image digest `36d453f80c2fd8af990eab43f9030c3da1e0992b247aaaf742b31aff9c3bcea4`, exclusive flock, worker command/environment checks, version-resolved existing secret bindings, and actual HTTPX transmitted byte count. These address the identified structural findings in principle. Final approval remains withheld pending the final prepared hashes and old-process loaded-environment equality checks. Resolve apply-time admin/client/intake reads through the prepared version bindings as well; do not re-resolve an unversioned latest secret after preparation. Return and check the snapshot's complete app resource identity. Final script/preparation must be re-reviewed after these edits; the original reviewed hashes above are historical only.

The intended sequence denies external intake, waits past the configured pre-reservation deadline, checks quiet same-process snapshots repeatedly, floors fresh account estimates without refunds, version-pins the new seed, deactivates the old revision, and verifies absent old replicas before promotion. It preserves the full template/configuration except image/revision/new-seed changes, then verifies same-process acceptance and exact ingress restoration. Acceptance deliberately forces local 422 before provider dispatch and checks unchanged credit groups; it does not prove provider giant-input acceptance. No stale rollback or automatic application replay is implemented. These are reviewed code intentions, not live validation evidence.
