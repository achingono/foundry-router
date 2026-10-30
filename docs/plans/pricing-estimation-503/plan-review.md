# Independent plan review

Verdict: **Approved** after amendment and independent re-review of `activities.md` on 2026-10-29. Reviewed before implementation in a separate reviewer session. Reviewer did not author the plan or implementation. Approval covers the amended plan, not implementation or production execution.

## Reviewed scope

Reviewed all six planning artifacts in this directory, current `AGENTS.md`, the contextual deep-review prompt, estimator and selection/error paths in `src/foundry_router/credit.py` and `src/foundry_router/routing/__init__.py`, bounded intake/configuration, existing credit tests, and canonical API, routing, configuration, testing and operations documentation. Git status contained only this plan and the separate untracked `responses-request-limit` plan; no implementation diff existed. The latter plan was not modified or approved.

The reproduced estimator/intake mismatch supports a local correction; the plan appropriately does not claim proof of the original Desktop request's exact cause. Compact UTF-8 serialization, unchanged intake, depth bounds, conservative accounting, explicit failover settlement and mocked forwarding coverage are appropriate. Quota remains separate from credit; no provider, arbitrary-pool, retry or streaming lifecycle redesign is authorized.

## Findings

### Major — Distinguish request failures from every pricing/configuration failure

- **File/Module:** `activities.md:5`; `src/foundry_router/credit.py:408-467`.
- **The Issue:** “With valid prices” follows “token pricing” and can be implemented as valid input/output token prices plus any `None` estimate becoming 422. Existing image/audio estimation also returns `None` for missing or mismatched media price ceilings and profile configuration with otherwise valid token prices.
- **Why Static Analysis Missed It:** This is an HTTP/business classification contract across independently valid configuration dimensions, not a type or syntax error. No scan was run for this plan review.
- **Impact:** Server-side pricing/configuration outages could become client errors, giving misleading remediation and changing unrelated media behavior.
- **Recommended Fix:** Explicitly classify known request-estimation failures (bound/depth/serialization and invalid output shape) as 422, retaining 503 for pricing/configuration failures and unknown failures. A narrow typed internal failure reason/result or shared request-validation result is preferable to inferring cause solely from token-price validity. Preserve existing estimator callers as appropriate. Add regressions for valid token prices with media pricing/profile estimation failure retaining 503, plus valid pricing and known request failure yielding 422 with no reservation/egress. Amend the plan before implementation and obtain re-review.

### Suggestion — Test the exact intake edge and synthesized serialization fields

- **File/Module:** `activities.md:4-6`; `src/foundry_router/credit.py:577-585`.
- **The Issue:** Compact serialization removes whitespace amplification, but the estimator synthesizes `tools: []` and `text: null` even when absent. Its serialized object is not exactly the accepted wire object.
- **Why Static Analysis Missed It:** This requires comparing two serialization contracts at their size boundary.
- **Impact:** A remaining narrow estimator/intake mismatch is possible near the cap, especially for short arbitrary model names.
- **Recommended Fix:** Include an exact configured-cap API case with short model names and omitted optional fields. Avoid synthesized absent keys or account explicitly for bounded estimator-only overhead. Record disposition; do not increase accepted intake.

## Remaining gates and authority

Amendment disposition: the Major finding is resolved by the checked estimator's narrow request exception, compatibility wrapper, and explicit retention of 503 for media pricing and unknown failures. The serialization suggestion is accepted: only present keys are serialized, and a bounded two-times character-cap allowance covers JSON normalization while charging every serialized byte. Intake remains unchanged. Implementation verification must include media failure classification and exact-cap/normalization cases described above; the increased serialization allowance applies to configured Responses only, preserving absent-settings and embeddings compatibility. No unresolved Critical or Major plan findings remain.

Focused/full tests, measured coverage >=80%, lint, format, mypy, applicable Docker checks, relative-link validation, final diff and independent implementation deep review remain outstanding. `scripts/quality/sonarqube-scan.sh` is absent in this checkout; no successful Sonar scan is claimed, and the repository's scan gate is conditional on its presence.

The production step is a separate exact-packet review gate, not deployment approval from this review. Its planned closure/drain/fresh per-account seed/stopped-old-writer sequence matches operational requirements. The packet must demonstrate current authority, admission closure before the final snapshot, pinned configuration/seeds, no stale rollback, memory/one with one worker, and exact ingress restoration without an unnoticed process restart. Local mocked successful large-input forwarding and production rejected no-egress input establish different outcomes; neither proves provider acceptance of giant input. No tests, Azure evidence, live pricing or production mutations were independently executed by this reviewer.
