# Independent contextual implementation review

Verdict: **Approved for reviewed local implementation; live gates remain outstanding**. October 13, 2026. This reviewer authored neither the implementation nor the plan; only review artifacts were edited.

## Scope and evidence

Read `.agents/prompts/deep-review.prompt.md` and applied its contextual scope. Inspected current git status and actual tracked/untracked implementation: Anthropic adapter, provider configuration/registry/backend transport/translated forwarding, preserved Argon additions, eighteen-slot runner, Anthropic and runner unit/integration tests, amended plan/review, canonical configuration/operations/requirements changes, prior handoff evidence, inherited CompatibleTextAdapter/public builder and bounded SSE reader.

The Sonar scanner script is absent; this is not a successful scan. Coordinator evidence reports full suite 2647 passed / 3 skipped / 19 deselected, runtime coverage 90.20%, initial runner coverage 89.86%, Ruff lint/format and strict mypy passing. Those full-run figures were not independently re-executed here. This reviewer directly ran the focused Anthropic/runtime/runner suite after the first correction: **62 passed**, including the over-bound runner regression. No paid inference or Azure mutation was performed by this reviewer.

## Findings

### Major — failed final validation retained a passed outcome (resolved)

- **File/Module:** `scripts/quality/opencode_five_validation.py:306` through the exception handler.
- **The Issue:** The runner set status to passed before validating final numerics. A validation exception only changed error_category, so execute continued to the next slot. A completed response with matching debit but output tokens above the request bound triggered this.
- **Why Static Analysis Missed It:** The logical ordering of acceptance publication, exception recovery and authorization of subsequent paid calls is a business state-machine invariant.
- **Impact:** Additional inference could occur after a failed bounded acceptance, contradicting halt-on-failure authority.
- **Recommended Fix:** Reset status to failed for every handled failure, or publish passed only after all validation succeeds. Add an over-bound usage response with matching debit and assert exactly one dispatch, durable failure and replay refusal.
- **Disposition:** Coordinator added an explicit failed status in the exception handler and the over-bound regression. Independently inspected and included in the 62 passing focused tests. Resolved; reviewer did not implement the fix.

### Major — nullable public token bounds become invalid native fields (resolved)

- **File/Module:** `src/foundry_router/api/adapters/opencode_anthropic.py:103` (related optional sampling handling at lines 58 and 107).
- **The Issue:** Shared request validation accepts explicit null max_output_tokens, but native assembly sends max_tokens:null instead of the configured default. Anthropic requires a positive max_tokens. Nullable sampling fields similarly pass through or trigger a dual-parameter rejection solely because both keys exist.
- **Why Static Analysis Missed It:** Both dictionaries are valid Python; the mismatch is between the public nullable contract and the native provider contract.
- **Impact:** Valid ordinary text client requests with explicit null defaults fail after unnecessary provider admission/dispatch; clients serializing optional nulls behave differently from clients omitting them.
- **Recommended Fix:** Normalize null max_output_tokens to default_output_tokens; omit null sampling fields and only reject dual non-null sampling values. Add request/default regression tests.
- **Evidence:** Reviewer executed the adapter with input x and max_output_tokens null: check_request returned None, assembled native max_tokens was None.

- **Disposition:** Coordinator normalized explicit null token limits to the configured default, omitted null sampling values and limited dual-sampling rejection to non-null values. Independently inspected the correction and its regression; final focused rerun **63 passed**. Both Major findings are resolved without reviewer implementation edits.

## Contextual assessment

Business intent is appropriately scoped to a model-agnostic nonstream Messages provider; Sonnet streaming is blocked at both pool policy and adapter capability. Cache-inclusive usage retains real token counts and the planned 4 USD/M input ceiling deliberately overestimates ordinary/read cost. Known valid usage is extracted before rejecting malformed output. Provider model/auth/version ownership stays in the backend boundary; caller native/cache/tool/thinking fields are rejected. Single-shot translated forwarding retains existing conservative dispatched-failure settlement and bounded cooldowns; no new post-output retry path is introduced. Quota and credit remain separate, with one account across arbitrary model pools.

Bounded text/parser/response ceilings and transport reuse avoid new unbounded buffering or client lifecycle state. The runner uses atomic consumed slots under an exclusive file lock, preserves ambiguous reservation state, rejects replay and checks configuration plus model/provider/credit ownership before each dispatch. Its image digest argument and admin configuration projection are scoped attestations, not independent proof of the running image or the full secret/config bundle; the external immutable release packet remains necessary.

## Remaining gates

- Both Majors are independently cleared; refresh final verification evidence after all changes.
- Immutable Linux/amd64 image build and exact release/config/secret bindings remain pending in supplied evidence. No Docker or Azure runtime success is inferred.
- Before live execution, review the concrete packet and prove the targeted exec preflight, actual effective admission barrier/no bypass, memory process continuity, final drained snapshot and stopped writers. Active production traffic cannot be treated as quiet.
- Staging 0.10 USD and production 9.90 USD are disjoint conservative seeds; no unused staging transfer is authorized automatically. Eighteen live slots, stopped staging, production acceptance and exact original ingress restoration remain outstanding.
- Finish relative-link/secret/final-artifact checks and synchronize final measured evidence. Material runtime or operational scope changes require review of the changed scope.

## Pending handoff amendment

The coordinator proposed policy fingerprints excluding inherited production initial seeds, because those values can only be captured after the barrier. This is a sound narrow design if OpenCode fixed 0.10/9.90 seeds remain bound, all policy/topology/cycle/reserve fields remain immutable, and a separate immutable final handoff artifact binds the final all-account snapshot/seed payload to the same image and policy-manifest digest before promotion. Exact private config/secret comparisons remain mandatory. This paragraph approves the design only; changed runner code and the concrete release packet must still be inspected.
