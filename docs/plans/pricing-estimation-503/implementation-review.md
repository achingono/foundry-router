# Independent contextual implementation review

Verdict: **Approved for code scope; verification and production gates remain open.** No Critical or Major code findings. Separate reviewer session, 2026-10-29; reviewer authored neither implementation nor approved plan. This report does not approve deployment.

## Scope and evidence

Reviewed actual working-tree diff in `src/foundry_router/credit.py`, `src/foundry_router/routing/__init__.py`, `tests/unit/test_credit.py`, `tests/unit/test_main.py`, and canonical API/configuration/observability/requirements-traceability documents against the amended approved plan. Read `AGENTS.md` and `.agents/prompts/deep-review.prompt.md`; followed relevant unchanged media estimation, request parsing, initial selection and failover settlement interactions. Separate untracked `responses-request-limit` work was excluded.

Scan evidence checked first: `scripts/quality/sonarqube-scan.sh` is absent, so no Sonar success is claimed; its repository gate is conditional. Coordinator reports 130 focused tests, Ruff lint/format, mypy (76 files) and Docker build passed. Reviewer independently ran `.venv/bin/python -m pytest tests/unit/test_credit.py tests/unit/test_google_audio_output_credit.py -q`: **46 passed**. Full-suite coverage and Azurite evidence were pending when reviewed, and coordinator results are not independent executions by this reviewer.

## Contextual assessment

- Business intent: larger accepted ordinary/tool requests reach the mocked backend, while a known invalid output limit returns a sanitized 422 with no backend call, reservation or debit. Missing token pricing retains 503. Media estimation branches return before the checked text path, preserving their existing pricing failure behavior.
- Concurrency/lifecycle: rejection occurs before credit/quota reservation. The compatibility wrapper preserves None-returning behavior for existing estimation and failover quota callers. Existing first-attempt settlement, single-writer state and post-output streaming retry restrictions are unchanged.
- Architecture/trust boundaries: estimation remains in credit and HTTP translation in routing. Exception messages are fixed strings, without request content. No credentials, endpoints or provider-specific pool choices are introduced in implementation. Quota and estimated dollars remain separate.
- Resource economics: intake still bounds raw bodies, parser depth limits remain, and text walking threads its explicit bound through recursive calls. Compact serialization charges every projected UTF-8 byte plus framing; omitted fields are not synthesized. The two-times normalization allowance is bounded, but—as before—serialization materializes before its size check; this change does not establish a new peak-memory benchmark for the maximum configured intake.
- Maintainability/traceability: checked API plus compatibility wrapper is a small local change. Documentation distinguishes locally implemented behavior from pending production acceptance and does not claim that giant requests are accepted by providers.

## Suggestions requiring disposition

### Suggestion — Exercise media failure through the checked entry point

- **File/Module:** `tests/unit/test_credit.py:205`; `tests/unit/test_google_audio_output_credit.py:46`.
- **The Issue:** Existing media tests invoke the compatibility wrapper. They would still pass if a future change incorrectly raised the new request exception, because the wrapper catches it. New checked-pricing coverage covers token prices only.
- **Why Static Analysis Missed It:** Both failure modes are type-correct; their HTTP meaning differs.
- **Impact:** The specifically approved media-503 guarantee lacks a direct regression at the new boundary.
- **Recommended Fix:** Test the checked estimator with valid token prices and absent/conflicting media prices, asserting None without exception; preferably also exercise routing's 503 result. Code inspection currently supports the correct behavior.

### Suggestion — Exercise exact cap through API intake

- **File/Module:** `tests/unit/test_credit.py:157`; `tests/unit/test_main.py:1254`.
- **The Issue:** Exact-cap normalized-number coverage tests estimation directly, while API forwarding uses a below-cap request.
- **Why Static Analysis Missed It:** Cross-layer accepted-byte boundaries require runtime integration evidence.
- **Impact:** The test suite does not yet demonstrate the exact intake boundary and estimation boundary together.
- **Recommended Fix:** Submit raw JSON at the configured byte cap with compact tools and numeric normalization through the API; verify successful mocked forwarding, and retain existing over-cap rejection coverage.

## Remaining gates

Follow-up disposition: both suggestions are addressed. Reviewed the added checked MAI missing-media-price regression (valid token prices, None without exception) and actual raw exact-intake-cap API request reaching its mocked backend once. Numeric normalization retains separate estimator coverage. No new implementation changes were introduced by these tests. Updated incident evidence records coordinator-reported expanded focused **132 passed**, full **2,884 passed / 3 skipped / 19 deselected, 90.45% coverage**, real Azurite **15 passed**, Ruff lint/format, mypy **76 files**, and native Docker build plus liveness/readiness and synthetic large-input 422 with zero debit/reservations. These are coordinator-provided results, not reviewer reruns. The stale incident-status observation below is resolved.

Record completed full suite and measured coverage >=80%, Azurite/applicable Docker health checks, link validation and final evidence/diff review. The current incident evidence file still says no source change and must be updated to accurately report implementation and measured checks. Production requires its own reviewed immutable-image handoff packet, current authority, verified admission closure and drain, conservative fresh all-account seeds, no old writers/stale rollback, memory/one and exact ingress restoration with process continuity. No Azure validation was executed by this reviewer.
