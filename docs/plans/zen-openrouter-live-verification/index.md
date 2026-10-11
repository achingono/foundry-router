# Zen and OpenRouter live verification

**Planned.** No live dispatches have been made; no runtime code changes are
proposed in this phase. Independent plan review is required before any live
request. Live upstream compatibility is not established by the mocked
implementation in [the backends plan](../opencode-zen-openrouter/index.md).

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)

## Objective and contract

Establish scoped live evidence that the router's Zen pass-through and OpenRouter
translation paths work against real upstreams for operator-selected exact
models, with usage-matched local settlement and zero retained reservations.
Local estimates remain estimates; nothing here measures provider billing.

1. Three sequential stages with halt gates: Stage 1 Zen Responses
   (one non-streaming + one streaming request, one operator-selected
   Responses-model row, text-only, `max_output_tokens` at most 128).
   Stage 2 runs only after Stage 1 success is recorded: OpenRouter Responses
   (one non-streaming + one streaming request, one operator-selected exact
   namespaced model, same text bounds). Stage 3 runs only after Stage 2
   success: OpenRouter embeddings (one call, one operator-selected exact
   embedding model, short input). At most six live dispatches plus bounded
   read-only diagnostics; no retries, no alternative models, no production
   changes.
2. Credentials are operator-supplied out of band and live only in the executing
   environment (environment variables or token-authenticated vault reads).
   They are never committed, logged, displayed, or recorded in evidence. Client
   and router keys follow the same rule. A wrong or missing credential refuses
   before dispatch.
3. Requests use short nonsensitive text. Record only numeric/metadata outcomes:
   public and provider HTTP status, completion/output presence, input/output
   usage counts, local estimated debit at configured test prices, and
   admin-diagnostic reservation/inflight snapshots. Never record prompts,
   outputs, error bodies, or credential values.
4. Streaming is verified with terminal usage and preserved SSE frame boundaries;
   there is no retry after meaningful stream output. Any ambiguous dispatched
   failure halts its stage persistently pending review; the halt is recorded
   before any further dispatch.
5. Local estimated debits are computed at operator-approved test prices and are
   explicitly unrelated to provider billing. Success on one exact model says
   nothing about other models, tools/media, quota ceilings, provider admission
   traffic, Table-backed inference, or production readiness; those remain
   separately gated.

## Scope

### In scope

- Six bounded live dispatches across three gated stages plus read-only
  readiness/admin diagnostics against a dedicated test configuration.
- Numeric-only evidence and an independent review record.

### Out of scope

- Runtime code changes (unless a real defect is established by evidence, then a
  separately reviewed amendment first).
- Additional models, tools/media/structured output, quota or admission
  characterization, Table-backed verification, cost reconciliation, and any
  production configuration or deployment change.
