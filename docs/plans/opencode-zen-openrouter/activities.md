# Zen/OpenRouter activities

1. Independent plan review and finding disposition are recorded in
   [review.md](review.md); preserve the revised contract during implementation.
2. Extend `BackendConfig.provider` with `opencode_zen` and `openrouter`. Add
   per-provider validation: exact HTTPS API root with raw-path guards before
   URL normalization; operation-path/userinfo/query/fragment rejection;
   bounded nonblank `deployment` (namespaced IDs allowed only for OpenRouter,
   up to 512 UTF-8 bytes); Zen defaults `["responses"]` with embeddings
   rejected; OpenRouter defaults `["responses"]` with explicit embeddings
   opt-in; native surface and Google profiles invalid for both. Test
   cross-provider confusion (Zen root with chat suffix, OpenRouter root with
   Responses suffix, Azure/Google values on new providers).
   Document that selecting Zen declares operator-verified Responses model
   compatibility; local config validation does not consult the upstream catalog.
3. Implement Zen transport in the backend client: `{root}/responses` URL
   construction, `model` substitution only, Bearer injection, caller-auth
   stripping, exact origin/port/base-path confinement, redirects disabled.
   Preserve the accepted Responses body except for `model` (no Chat dialect).
   Reuse only wire helpers compatible with Zen's separate execution policy. Test with
   synthetic roots/ports/base paths.
4. Implement OpenRouter transport reusing the generic translated path:
   `{root}/chat/completions` and `{root}/embeddings`, `model` substitution,
   Bearer injection, same confinement. Never accept or forward OpenRouter-only
   fields (`provider`, `models`, `route`, `plugins`) or attribution headers
   from callers.
5. Wire adapter selection by actual provider: a dedicated Zen validator and
   pass-through adapter, and OpenRouter via the shared `CompatibleTextAdapter` hooks
   with independent bounded validation and no Google helper imports. Keep
   Google native/media branches confined to Google. Implement Zen's explicit
   stateless-text allow-list and bounds in the contract, rejecting unsupported
   fields and foreign wire shapes before any Zen quota/credit reservation or
   dispatch. Do not inherit Azure's unconditional `check_request()` acceptance.
6. Separate wire handling from attempt policy: Zen preserves Responses/SSE bytes
   with bounded usage inspection; OpenRouter translates Chat responses with the
   actual provider adapter. Both use single-shot execution independent of
   `retry_attempts`, 429-only pre-output routing failover, terminal 401/403 error
   cooldown, and conservative dispatched-failure/cancellation settlement. Track
   known usage and dispatch state through body reads, stream ownership transfer
   and cancellation; close upstreams and finalize reservations exactly once.
   Do not inherit Azure retries or failure refunds. Keep Azure behavior unchanged.
7. Add mocked-upstream ASGI tests for both providers: normal/streaming
   Responses, OpenRouter embeddings, mixed pools/aliases, operation filtering,
   429/auth/5xx, malformed envelopes, post-output failure, cancellation,
   missing usage, cleanup, and redaction. With `retry_attempts > 1`, verify one
   dispatch on 5xx/transport/protocol/auth failures, no alternate dispatch, known
   usage or full-estimate charges for ambiguous failures, and zero outstanding
   reservations. Exercise cancellation before dispatch, after dispatch, before
   first output and after output. For 429, assert separate admissions and quota
   counts for two attempts, first-attempt credit refund and second settlement.
   Test Zen foreign fields both alone and alongside valid `input`, nested
   unsupported content, bounds, and false-only flags; assert zero reservations
   and egress in Zen-only pools and capability filtering in mixed pools. Verify
   accepted Zen bodies remain unchanged except for `model`. Run unchanged Azure,
   Google and generic lifecycle tests/oracles.
8. Update configuration, API, security, architecture, operations, and
   requirements traceability with exact local scope (mocked verification;
   live gates separate). Run focused/full tests with >= 80% coverage,
   Ruff/mypy, Docker build/smoke, conditional SonarQube, contextual review,
   links, and final diff. Commit the phase transition.

## Review focus

- Provider-key ownership (no Azure/Google/generic fallthrough or shared-literal confusion).
- Exact root/auth ownership and confinement for two new roots.
- Pass-through vs translation separation (Zen never sends the Chat dialect;
  OpenRouter never bypasses bounded translation).
- Unsupported-field rejection before admission (Zen non-Responses wires;
  OpenRouter routing/plugin/attribution extras).
- Conservative billable failures and no post-output retry.
