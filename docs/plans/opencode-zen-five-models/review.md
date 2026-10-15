# Independent plan review

Verdict: **Approved — amended plan only** (October 13, 2026). This reviewer authored neither the plan nor implementation. Review-only; existing Argon changes preserved.

Reviewed artifacts: `index.md`, `inputs.md`, `activities.md`, `outputs.md`, `exit-criteria.md`, `risk-register.md`, `evidence.md` in this directory; current `git status`; `.agents/prompts/deep-review.prompt.md`; `docs/development/testing.md`; `docs/operations/shared-resource-credit.md`; prior Argon deployment packet and OpenRouter production deployment evidence; provider config/backend/adapter/forwarding interactions, `CompatibleTextAdapter`, adapter usage protocol and `scripts/quality/production_two_validation.py` immutable ledger primitive.

The narrow nonstream Anthropic provider and eighteen explicit staging/production cases are justified feature-local scope. The plan preserves arbitrary pools, quota/credit separation, bounded intake/transport/retries, server-owned credentials/model selection, no downstream-output retry, safe redaction, memory/one production and stopped stale staging. Focused/full tests, >=80% coverage, lint/format/mypy, Docker, conditional scan, deep review, documentation and traceability gates are included.

## Initial findings and independent re-review

Re-reviewed amended `index.md`, `inputs.md` and `evidence.md` on October 13. Both initial Major findings below are **resolved at plan level**. Sonnet now uses a documented 4.00 USD/M input ceiling and real cache-inclusive token counts. The final snapshot follows a tested ingress deny barrier while the same memory process remains readable through targeted localhost exec; continuity, denial/no-bypass, drain and stopped writers are explicit proof gates. Acceptance allows only one controlled executor after the old writer is stopped, and original ingress policy is restored after acceptance. User allocation confirmation is recorded as 10 USD with 0.05 USD/5% reserve. These are planned controls, not claims that Azure behavior or inference has passed.


### Major — cache write estimate can undercharge

- **File/Module:** `index.md:23` (and roster price at line 11).
- **The Issue:** Ordinary input pricing is described as conservative for both cache read and cache creation tokens. Anthropic cache creation pricing can exceed ordinary input pricing; the plan has not established an OpenCode cache write ceiling or separate settlement pricing.
- **Why Static Analysis Missed It:** Provider billing semantics and the conservatism of deployment price inputs are external business rules.
- **Impact:** Valid cached responses may debit too little local credit and transfer an overstated remaining estimate into production.
- **Recommended Fix:** Bind documented conservative cache write pricing before live use. A minimal solution is a conservative configured input price covering the maximum supported cache-write multiplier for every actual input token; keep public usage as real token counts, reject client cache controls, and test cache-inclusive valid/malformed-response settlement. Document deliberate ordinary/read overestimation.

### Major — final memory snapshot requires an admission barrier

- **File/Module:** `index.md:31`.
- **The Issue:** Quiet admin observations followed by revision deactivation do not exclude new intake between snapshot and shutdown. Fresh memory estimates cannot be read from a stopped process, so the stated stop-then-capture order is insufficient.
- **Why Static Analysis Missed It:** This is an operational concurrency/lifecycle race across the control plane and the in-memory credit ledger.
- **Impact:** A request admitted after the final observed snapshot can consume provider credit without a corresponding reduction in the next revision's seed.
- **Recommended Fix:** Specify a supported admission barrier, drain and final readable snapshot before stopping all old writers. If intake cannot be excluded, explicitly use conservative seeds accounting for the uncertain interval, including zero for uncertain account balances rather than promoting the last quiet snapshot. Preserve all model/config ownership and do not silently claim quiet reads prove exclusivity.

## Remaining gates

Changed-scope implementation may proceed under this amended plan. Live rollout remains conditional on immutable exact release/config/request binding, runner/code review and measured verification, staging acceptance, proven admission-barrier feasibility/continuity and stopped-writer handoff, then production acceptance. Neither ingress deny semantics nor targeted exec/process continuity has been validated by this reviewer; failure must halt without promoting stale memory seeds. Material changes invalidate approval for the changed scope. The Sonar script is absent in the inspected tree; no scan success is claimed. No tests or live inference were run by this review. Public catalog/pricing and historical deployment claims were read as supplied evidence, not independently re-proven.

## Suggestion disposition

The risk register still labels the current allocation as missing. This is a documentation synchronization suggestion; `index.md` and `inputs.md` now bind the confirmed amount. Coordinator should mark that input risk resolved while retaining live binding as a required gate. No unresolved Critical or Major plan findings remain.
