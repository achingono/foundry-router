# Independent contextual implementation review

Verdict: **Approved for local implementation scope**. October 13, 2026. No Critical or Major code findings. Live deployment is not approved by this review. Reviewer is independent of plan authorship and implementation; this session previously reviewed, but did not author, the plan.

## Scope and evidence

Applied `.agents/prompts/deep-review.prompt.md` to the actual working diff: `src/foundry_router/config/__init__.py`, `backends/__init__.py`, `api/adapters/__init__.py`, `forwarding/__init__.py`; new `tests/unit/test_opencode_google.py` and `tests/integration/test_opencode_google_integration.py`; canonical configuration, operations, documentation hub and requirements traceability updates. Compared against the approved plan and existing native Google adapter, route admission, request construction and translated settlement/error handling. Inspected the planned deployment packet, configuration delta and acceptance manifest without executing them.

Scan evidence first: `scripts/quality/sonarqube-scan.sh` is absent. No successful Sonar scan is claimed; the repository's conditional scan obligation is not triggered. Inspected `/private/tmp/argon-full-tests-verified.log`: 2,586 passed, three skipped, nineteen deselected, runtime coverage 90.12%. Inspected final focused log: 55 passed. Coordinator also reports 108 focused regressions passed. Independently ran Ruff lint, formatting check and mypy over runtime source and the new tests as applicable: all passed; mypy checked 72 source files. `git diff --check` passed. Final Docker rebuild subsequently completed; inspected `/private/tmp/argon-docker-final.log` through successful image export. Inspected `/private/tmp/argon-container-smoke.log`: native OpenCode startup, liveness, readiness and model discovery returned success with network disabled; shutdown drained active requests. This is local smoke evidence, not inference evidence.

## Contextual assessment

- **Business intent and accounting:** The provider is model-agnostic, native text only, metered and thought-priced. Configuration rejects unsupported operations, Google free-tier failover and feature-profile expansion. Native usage translates candidate plus thought tokens; integration tests verify debit and cleared reservations for both wire modes. Catalog discovery is correctly distinguished from inference proof.
- **Concurrency and lifecycle:** New requests enter existing translated forwarding; 429 permits fresh routing admission, metered 5xx retains an estimate and cannot enter the Google free-tier exception. Auth failures cool down. Partial-stream tests demonstrate no failover and cleared reservations with conservative debit. The change adds no new reservation owner, background task or stream lifetime.
- **Architecture and trust boundaries:** URL path and physical model validation precede transport construction; transport preserves the configured base and supplies server-owned Bearer credentials. Native Google retains its existing `/v1beta` and Google auth behavior. Caller credentials are stripped, redirects are forbidden and raw public Google fields are rejected. Error-only adapter lookup has a safe default native profile, exercised by status/error tests. Profile checks at config and adapter selection prevent media/tools/continuation expansion.
- **Resource economics:** Existing bounded intake, native history/parser bounds, output limit and reservation deadlines remain in force. Quota and credit remain distinct. Planned production account handoff prohibits concurrent account writers and stale balance rollback. Pricing is explicitly an estimate.
- **Maintainability and claims:** The change reuses native parsing and settlement rather than duplicating them; changes remain at owning boundaries. Canonical docs describe mocked implementation and planned live acceptance without claiming Argon deployment. No secret values were found in the reviewed diff; test credentials are synthetic. Packet markers are explicitly non-deployable.

## Findings

No Critical or Major findings.

**Suggestion — preserve the planned packet inputs in versioned artifacts**

- **File/Module:** `deployment-packet.md`, lines 5 and 13, and its `configuration-delta.json` / `acceptance-manifest.json` links.
- **The Issue:** At inspection both JSON files were ignored by Git, so a fresh clone would lose the linked exact delta and acceptance hashes.
- **Why Static Analysis Missed It:** Ignore policy and operational document retention are outside runtime type/coverage checks.
- **Impact:** A recipient cannot reproduce the reviewable packet from repository contents alone.
- **Recommended Fix:** Retain the JSON in tracked Markdown or narrowly allow-list these two intended source artifacts. Preserve exact request/hash serialization and label the runner/live bindings Planned.
- **Disposition:** Resolved. Inspected two exact `.gitignore` exceptions for these packet JSON files and confirmed both appear in `git status --untracked-files=all`. Their repository inclusion is now permitted; no broad capture-retention exception was added.

The prior plan-review acceptance specificity suggestion is reflected in the manifest requirements: exact image/config binding, durable reserve-before-egress slots, meaningful text, terminal completion, thought-inclusive usage/settlement and zero reservations. Independently checked all four request SHA-256 hashes and the delta byte hash; they matched the inspected files. The runner implementing those requirements does not exist in this scope and still requires separate review.

## Remaining gates

Local final verification is complete for this change. Final Docker build and smoke evidence were inspected, `evidence.md` retains measured verification and limitations, final plan-folder relative document targets resolve, and `git diff --check` passes. The packet-retention suggestion is closed. The nineteen deselected tests and three skips are not claimed as passed. No real provider/Azure inference evidence was generated or independently verified by this review.

Fresh intake/account inputs, current quiescent all-account seed, reviewed durable runner, immutable Linux deployment image/config bindings, coherent pinned secrets, live staging compatibility and production acceptance remain open. Preserve memory state, one worker and maximum one replica; do not start existing staging with stale account estimates. Any runtime amendment requires review of the changed scope; no live execution authorization follows from this local implementation verdict.
