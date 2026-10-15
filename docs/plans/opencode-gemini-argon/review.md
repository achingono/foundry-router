# Independent plan review

Verdict: **Approved for implementation**. October 13, 2026. This is a fresh independent review session; reviewer did not author the plan or implementation. This is not approval to dispatch acceptance traffic or promote production.

## Reviewed scope

Reviewed `index.md`, `inputs.md`, `activities.md`, `outputs.md`, `exit-criteria.md`, `risk-register.md`, and `evidence.md` in this folder against the supplied AGENTS.md, canonical operations/testing documentation, and the last `openrouter-production-two/deployment-evidence.md`. Git status contained only this untracked plan folder; tracked implementation diff was empty.

Inspected current config validation in `src/foundry_router/config/__init__.py` and `google_features.py`, URL/header/payload construction in `backends/__init__.py`, adapter selection in `api/adapters/__init__.py`, native request validation/usage/translation in `api/adapters/google_native.py`, and translated forwarding selection, settlement and failover in `forwarding/__init__.py`. Reviewed existing native thinking tests and located the native integration and Zen config/transport/forwarding suites. Read `.agents/prompts/deep-review.prompt.md` and applied its contextual categories to the proposed design.

The explicit provider is appropriate: existing Zen routes Responses unchanged, whereas existing native Google inserts `/v1beta` and uses `x-goog-api-key`. Neither is an accurate transport for this contract. Reusing the native text adapter with provider-specific transport/auth and translated forwarding preserves ownership without creating another translation/accounting implementation. Metered-credit enforcement and exclusion from Google's free-tier 5xx exception preserve account economics. No quota/credit conflation or arbitrary pool restriction is proposed. Native low/minimal text restriction, thought-token settlement, safe URL validation and post-output no-retry rules are explicit. Production memory/one, no concurrent account writers, fresh quiescent credit handoff and stopping staging address the current lifecycle hazards.

## Findings

No Critical or Major plan findings.

**Suggestion — acceptance packet specificity**

- **File/Module:** `docs/plans/opencode-gemini-argon/index.md`, production contract (four acceptance slots).
- **The Issue:** The plan correctly requires durable slots, exact staging success and immutable bindings; executable slot ownership, invocation hashes, thought-inclusive usage assertions and cancellation cleanup evidence are still to be specified in the deployment packet.
- **Why Static Analysis Missed It:** These are live operational bindings and accounting observations, not static source properties.
- **Impact:** A loosely prepared packet could consume a slot against the wrong revision or call a truncated/thinking-only response a successful text acceptance.
- **Recommended Fix:** Before live review, bind each slot to exact environment/image/config/model/request hash and require meaningful public text, terminal stream completion, native thought-inclusive usage, matching estimated debit, zero residual reservations and clean writer shutdown. Record consumed/ambiguous outcomes durably; do not authorize replacement slots implicitly.
- **Disposition:** Track in deployment packet preparation; not an implementation blocker because the plan already requires independent packet review and exact successful staging before promotion.

## Remaining gates

Implementation must be independently reviewed against this contract and actual diff. Run focused then full tests with at least 80% coverage, lint, formatting, mypy, applicable Docker build, documentation link checks and secret/unsupported-claim review. The conditional `scripts/quality/sonarqube-scan.sh` is absent at this review; no scan was executed and no scan success is claimed. If present when verifying implementation, execute it and resolve required findings.

Provider documentation/catalog claims here were evaluated as recorded discovery evidence, not independent live inference evidence. Exact Argon thinking-level compatibility, streaming envelope, provider settlement, staging and production success remain unverified. Fresh account allocations/reserves, closed intake, current all-account seeds, immutable image and coherent secret bindings remain required. Review the concrete deployment packet and bounded acceptance evidence independently before production promotion. Material plan amendments invalidate this approval for changed scope.
