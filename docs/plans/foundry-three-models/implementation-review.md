# Independent contextual implementation review

Historical review: pending execution statements below describe the state at review. The scoped rollout subsequently passed; see [final production evidence](production-evidence.md).

**Verdict: Approved for the local implementation.** No Critical or Major implementation findings. This is not approval of an exact production packet.

Reviewer: independent `credit_plan_review` / `gpt-6-astra`; authored neither plan nor implementation. Reviewed actual tracked diff and new `azure_anthropic.py`, `azure_mai.py`, `config/foundry_models.py`, provider registration, backend route/auth assembly, configuration, credit estimates, forwarding, Responses intake, new 45-case test module and canonical documentation. Applied `.agents/prompts/deep-review.prompt.md` across business intent, resource/credit lifecycle, trust boundaries, architecture and maintainability.

## Findings and contextual conclusions

No Critical or Major code findings. The implementation is feature-local and retains arbitrary model pools and shared credit groups. Terra uses the existing Azure Responses adapter. Anthropic specializes existing bounded Messages conversion, injects both server-owned key headers and version, strips client auth/version/beta overrides, and preserves cache-inclusive token accounting without an invented cache discount. Unsupported operations and streaming fail closed.

MAI configuration requires a homogeneous, nonstream, unsigned pool, no token pricing or cached discount, and a positive per-image local estimate. Intake rejects unsupported fields before admission/dispatch and acquires a Linux inspection lease before exposing output capability. The fixed estimate remains intact through translated forwarding; absent usage cannot become zero debit. Confirmed pre-dispatch failure releases the reserve; ambiguous post-dispatch transport/inspection/cancellation paths retain charge. Existing translated routing owns bounded 429 failover; no ordinary retry follows ambiguous generation or delivered output.

The MAI projector requires the exact one-image envelope, canonical bounded base64, existing strict PNG inspection and digest/length identity before creating a completed image item. It returns usage=null, not fabricated token counts. The request owns the inspection lease until successful delivery ownership transfer; error/finally paths close it. Existing Google startup gates and strict worker format limits are unchanged. Exact live MAI output compatibility remains an acceptance gate, not a claim established by synthetic fixtures.

## Suggestions

- **Severity:** Suggestion.
- **File/Module:** `docs/configuration/index.md`, additional Foundry provider pricing paragraph; `docs/operations/shared-resource-credit.md`, MAI accounting paragraph.
- **The Issue:** Initial wording requires verified billing bounds and says the fixed estimate must cover actual billing, while the user has now approved an operator estimate without a proven Azure image-cost bound.
- **Why Static Analysis Missed It:** The distinction depends on the user-authorized monetary amendment, not code types.
- **Impact:** Readers could mistake the configured value for a verified Azure ceiling or believe the approved operator-estimate path remains blocked.
- **Recommended Fix:** State the accepted operator local estimate explicitly and distinguish it from a guaranteed or measured Azure billing ceiling.
- **Disposition:** Resolved: coordinator updated canonical configuration and operations wording; reviewer verified the operator-estimate distinction.

## Verification and remaining gates

Independently executed the 45 new regressions plus existing generated-image lifecycle and Anthropic integration cases: **62 passed**. Tests include endpoint/auth/model identity, invalid configuration, strict projection, exact API ledger charging and lease cleanup, worker errors, post-dispatch cancellation and confirmed pre-dispatch release. No source edits were made by reviewer.

Coordinator reports full 2,850 tests passed, 3 skipped, 19 deselected, 90.42% coverage; Ruff lint/format and mypy passed. Independent Docker health/readiness and built-image PNG-worker evidence passed, as recorded below. SonarQube script is absent, independently checked; this is not a successful scan. No Table schema change is introduced; Table production cut-over remains outside scope.

Exact production configuration, image/secret pins, operator-approved prices, memory-ledger handoff, spend-bounded acceptance and live PNG compatibility require separate packet review. No new production model registration or real provider inference is claimed here.


Reviewed source pins: tracked source diff SHA-256 `a74c9b61ecc0543337e7a2e965f3f6fc7b49c9095111a28da82ca566d94c2fa6`; new Anthropic adapter `34fa34cb428e0079dd7c8b0e462fa5efbf904f189d304113127684624dfce834`; MAI adapter `e6e130919afe769af908c78920c11d4918b8c00ba1fd9a7615804bb2a30c29ac`; pool validation `9f640e23640761f28e70d15dad5c7179ac8ffdb75c2fb2c1516db46cc7955170`; new tests `2e8c28ae3c4bca21de63e9bba03b6f6b9c213ade62db7550c045212bf1b51a29`.


## Final gate review

Reviewed [independent verification evidence](verification.md): full suite 2,850 passed / 3 skipped / 19 deselected at 90.42% coverage; final focused tests, Ruff/format/mypy passed. The verifier recorded final-image health and readiness HTTP200, Linux x86_64 worker inspection with 3,129 encoded bytes / 3,146,752 expanded bytes and verified digest, and temporary-container cleanup. Execution used local architecture translation, not native x86_64 hardware. Relative-link and whitespace checks passed. No Table-specific code or schema changed; this candidate's marker-excluded Azurite suite was not represented as a new pass.

The pricing-documentation suggestion is resolved. User-approved Sonnet and MAI values are explicitly local estimates, not guaranteed Azure billing ceilings; this amendment does not alter the generic implementation's credit lifecycle. There are no unresolved Critical or Major findings or outstanding local implementation gates. Production registration, exact-model provider behavior, real PNG compatibility, final monetary/configuration packet and guarded ledger handoff remain separate live gates. Approval does not authorize weakening the inspector or replaying ambiguous provider requests.
