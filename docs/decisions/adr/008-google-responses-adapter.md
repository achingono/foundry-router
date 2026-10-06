# ADR-008: Google Responses Compatibility Adapter

## Status

Accepted (implementation with mocked verification; real Google inference remains a separate opt-in gate).

## Context

Phase 09 routes Google AI Studio keys by project quota but forwards the public Responses body with only a `model` substitution onto Google's OpenAI-compatible `chat/completions` surface. The permissive fixtures return provider IDs without a real `choices[].message` envelope and do not require Chat `messages` upstream, so green mocks do not prove Responses compatibility. Streaming passes raw upstream bytes, embeddings omits the quota store, estimates ignore `instructions`, and Google retries follow the Azure 5xx policy, which risks duplicate billable generations.

Vendor references (verified 2026-10-05; pages may change, re-confirm before release):

- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai): base path `https://generativelanguage.googleapis.com/v1beta/openai/`, `chat/completions` and `embeddings` operations, `Authorization: Bearer <GEMINI_API_KEY>` on the compat surface, `max_completion_tokens` token limit, `stream_options: {"include_usage": true}` for streaming usage, `[DONE]` terminator with usage-only final chunks.
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): project/model/tier limits, input-token semantics, reset windows.
- [Responses reference](https://platform.openai.com/docs/api-reference/responses) and [streaming events](https://platform.openai.com/docs/api-reference/responses-streaming): pinned response fields, event ordering, terminal schemas.

## Decision

1. Add a typed provider adapter boundary under `src/foundry_router/api/adapters/` (protocol, Azure pass-through, Google translation). Adapters are pure except per-request stream state; no HTTP, stores, retries, credentials, or global conversation state.
2. Resolve the adapter from the selected backend provider per attempt from the immutable public request, so failover never feeds one provider's transformed body to another.
3. Add `supported_operations` to `BackendConfig` (Azure defaults `["responses", "embeddings"]`, Google defaults `["responses"]`; Google embeddings entries declare `["embeddings"]`). Filter identically on initial selection and failover before either store reserves; return `unsupported_operation`/`unsupported_parameter` before egress while keeping capable Azure candidates eligible.
4. Translate text Responses, stateless text history, instructions, streaming, usage, and text embeddings per the first-release matrix in the [adapter plan](../../plans/google-ai-studio-adapter/index.md); reject everything else explicitly. Send `Authorization: Bearer` with double-suffix-tolerant compat paths; strip client auth and reject credential-bearing query strings including `key`.
5. Read Google bodies incrementally with finite decoded-byte bounds; recalculate content headers; preserve only safe `Retry-After`/`Cache-Control`. Prefetch a validated translatable event before committing downstream SSE; latch no-retry at the first downstream event; enforce event/output/time bounds and the absolute reservation deadline.
6. Retry Google only on 429 (with project-group cooldown and bounded `Retry-After`); put 401/403 in backend-local `ERROR_COOLDOWN` without same-request cycling; treat 5xx, transport/read failures, truncation, and malformed schemas as terminal potentially-billable outcomes that settle known usage or the estimate exactly once.

## Consequences

- Google backends serve text Responses and embeddings through the existing API with explainable capability errors; unconfigured tool/media/schema features fail fast. ADR-010 adds opt-in unsigned tools, structured text and small PNG input; signed/additional media remain disabled.
- Estimates cover instructions/history/overhead and the reserved output bound is enforced upstream.
- Ambiguous Google dispatches never produce a second billable generation from one reservation.
- Real inference, provider failure traffic, and production cut-over remain separate unverified gates; the adapter must be reported as **Implemented** (mocked) with live validation **Planned** until W7 passes.

## Verification References

- Adapter contracts and bounds: `tests/unit/test_google_adapter.py`
- Routing/quota/retry integration: `tests/integration/test_google_adapter_integration.py`, `tests/integration/test_full_flow.py`
- Regression gates: `tests/unit/test_backends.py`, `tests/unit/test_config.py`, `tests/unit/test_forwarding_stream.py`, `tests/unit/test_main.py`
