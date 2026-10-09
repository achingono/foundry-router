# OpenCode Zen and OpenRouter backends

**Planned.** No runtime code changed in this phase; this is the concrete implementation
plan only. Live upstream compatibility remains a separate gate in all cases.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
- [Independent plan review](review.md)

## Objective and contract

Route configured logical Responses pools through two new explicit backend providers
without weakening the existing Azure/Google/generic contracts: OpenCode Zen as a
native Responses pass-through upstream (`POST {root}/responses`, Bearer auth) and
OpenRouter as a Chat Completions translated upstream (`POST {root}/chat/completions`,
Bearer auth, shared bounded text dialect). Reuse existing quota/credit separation,
single-shot attempt discipline, and redaction boundaries.

1. Admit `provider: opencode_zen` in `BackendConfig`. Endpoint is the exact configured
   HTTPS API root including the version path (for example
   `https://opencode.ai/zen/v1`); append only `/responses` for the Responses
   operation. Reject operation paths, userinfo, queries, fragments, and unsafe
   (encoded/dot/duplicate) path segments on the raw endpoint before URL
   normalization, following the existing `openai_compatible` raw-path guard.
   Require a bounded nonblank physical model identifier in `deployment`
   (Zen model ID such as `gpt-5.4`); namespaced slashes are out of scope for Zen
   (unlike generic compatible IDs). Default `supported_operations` is
   `["responses"]`; embeddings is not offered on this provider in this phase.
   Native surface and Google feature profiles are invalid. Credential remains
   externally supplied; strip caller auth/cookies/forwarding headers and inject
   server `Authorization: Bearer` only. Preserve exact origin/port/base-path
   confinement with redirects disabled.
   Selecting `opencode_zen` is the operator's declaration that the configured
   model supports Zen's `/responses` endpoint. The router validates syntax and
   declared operations, not membership in Zen's changing model catalog. Operators
   must select a Responses row from the endpoint table; misconfigured model
   families are not guaranteed to fail locally before admission. No catalog
   lookup, model-name inference, or hard-coded model allow-list is introduced.
2. Admit `provider: openrouter` in `BackendConfig`. Endpoint is the exact configured
   HTTPS API root (for example `https://openrouter.ai/api/v1`); append only
   `/chat/completions` for Responses or `/embeddings` when explicitly declared.
   Same raw-path/operation-path rejection as above. Require a bounded nonblank
   physical model identifier; namespaced body values such as `organization/model`
   are allowed up to 512 UTF-8 bytes (same bound as `openai_compatible`).
   Default operations are `["responses"]`; embeddings is explicitly declared via
   `supported_operations`. Native surface and Google feature profiles are invalid.
   Same Bearer-only server credential contract and confinement as Zen.
3. Zen Responses uses a dedicated request validator followed by wire pass-through:
   forward the validated public Responses body with only the `model` substituted by `deployment`, and
   forward SSE bytes unchanged with bounded terminal-usage inspection. No Chat
   translation dialect (`max_completion_tokens`/`stream_options.include_usage`)
   is sent to Zen. Initial request support is bounded stateless text: `model`,
   `input`, `instructions`, `metadata`, `max_output_tokens`, `temperature`,
   `top_p`, `stream`, and false-only `store`/`background`. Validate field types
   and values using the existing compatible text contract, with at most 128
   input history items, 128 parts per message and 256 KiB aggregate text.
   Accept only ordinary text histories; reject unknown top-level/nested fields,
   tools, structured output, media, stored continuation and provider state.
   Validation must not translate the accepted body or inject defaults into it.
   In particular, foreign `messages`, `contents`, `generationConfig`,
   `max_tokens`, `max_completion_tokens` and `stream_options` fields fail even
   when accompanied by a valid `input`. Rejections exclude this candidate before
   quota/credit admission and egress; other capable providers in a mixed pool
   remain eligible. A Zen-only pool returns a sanitized 422. Zen Anthropic,
   Google, `systemone` and Chat wires are out of scope. This request-shape gate
   does not establish the configured model's upstream wire compatibility.
4. OpenRouter Responses uses the existing fixed translated dialect: bounded
   text-only string/history input, instructions, metadata, and existing generation
   parameters via the shared `CompatibleTextAdapter` hooks (128 messages, 128
   parts/message, 256 KiB aggregate). Tools, structured-output extensions,
   media, stored continuation, and provider state are rejected before
   admission/reservation. OpenRouter-only extras (`provider.order`,
   `allow_fallbacks`, `models`/`route`, plugins, `HTTP-Referer`/`X-Title`
   attribution, BYOK) are never accepted from callers and never forwarded; the
   router selects the configured backend deterministically as today. Streaming
   requires the Chat `[DONE]` terminator and shares the bounded Responses
   lifecycle decoder; no failover occurs after any downstream event.
5. Single-shot attempts for both providers; only pre-output 429 permits routing
   failover (admitted fresh, both attempts counted against quota groups where
   configured); no retry after any downstream event. Ambiguous dispatched
   5xx/transport/protocol failures retain known usage or the full estimate and
   terminate. Auth failures (401/403) enter backend-local `ERROR_COOLDOWN`
   without credential cycling. Quota and credit remain separate concepts;
   existing `quota_group`/`credit_group` configuration applies without
   provider-derived balances. Logical models and aliases determine pools, with
   arbitrary backend counts and mixed Azure/Google/generic/Zen/OpenRouter pools
   subject to operation filtering. No infrastructure or production change, and no
   live upstream availability claim in this implementation phase.

Zen's wire pass-through is independent of its execution policy. Do not reuse
Azure's retry loop or failure-refund behavior. Both new providers make one dispatch
per selected backend regardless of `retry_attempts`; only a pre-output 429 can
request fresh routing admission. Both streaming and non-streaming paths must
retain dispatch/usage facts across cancellation, response reads and cleanup.
Confirmed pre-dispatch failures release reservations; dispatched ambiguous
failures retain valid known usage or the full estimate, close the upstream and
finalize reservations once. Missing/invalid usage must not imply zero cost.
401/403 are sanitized terminal rejections with backend-local error cooldown;
429 refunds credit for the rejected attempt but retains its quota attempt count.
Neither case cycles credentials internally. Successful wire pass-through and
bounded SSE usage inspection may share helpers with Azure, whose existing retry,
adapter and accounting behavior must remain unchanged.

Independent plan review on 2026-10-09 found two Major issues, addressed in this
revision; the [review record](review.md) clears the revised plan for implementation.
Implementation review, full tests (coverage >= 80%), Ruff/mypy,
Docker build/smoke, links, and final diff establish implemented code. Actual
upstream/model/client compatibility remains a separate live gate.

## Scope

### In scope

- `opencode_zen` bounded stateless-text Responses validation and wire pass-through
  (config, Bearer transport, SSE pass-through, tests, docs).
- `openrouter` Chat/embeddings translation via shared bounded text hooks
  (config, Bearer transport, lifecycle decoder selection, tests, docs).
- Adapter selection by actual configured provider; mixed pools, aliases, and
  operation filtering preserved.
- Conservative settlement, redaction, and single-shot failover semantics for
  both providers.

### Out of scope

- Zen `/messages`, `/models/*`, `/systemone`, and Zen chat-models translation
  (follow-up only with explicit capability + live gates).
- Zen tools, structured output, media, stored continuation and background work;
  broader Responses request support requires a separately reviewed extension.
- OpenRouter provider-preference routing, plugins, attribution headers, BYOK,
  and any non-`float` embeddings encoding.
- Live credentials, live upstream verification, production enablement, and
  infrastructure changes.
