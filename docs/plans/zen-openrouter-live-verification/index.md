# Zen and OpenRouter live verification

**Planned.** No live dispatches have been made; no runtime code changes are
proposed in this phase. [Independent plan review](review.md) is complete; its
findings are addressed at the planning level. Harness implementation, offline
validation and implementation review remain required before any live request.
Live upstream compatibility is not established by the mocked implementation in [the backends plan](../opencode-zen-openrouter/index.md).

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risk register](risk-register.md)
- [Evidence](evidence.md)
- [OpenRouter-only amendment (proposed, pending review)](amendment-openrouter.md)
- [Paid-models amendment (Planned live verification; independent review gate cleared)](amendment-paid-models.md)
- [Direct-probe amendment (Planned live diagnosis; independent review gate cleared)](amendment-direct-probe.md)
- [Reasoning-tolerance amendment (proposed, pending review)](amendment-reasoning-tolerance.md)
- [Independent direct-probe commit review](review-direct-probe-607da09.md)
- [Independent paid-models commit review](review-paid-models-6d5a799.md)
- [Independent plan review](review.md)

## Objective and contract

Establish scoped live evidence that the router's Zen pass-through and OpenRouter
translation paths work against real upstreams for operator-selected exact
models, with usage-matched local settlement and zero retained reservations.
Local estimates remain estimates; nothing here measures provider billing.

Run A covers Stages 1–2 under run `zen-openrouter-live-2026-10-11`. Its Zen
case halted on provider 403 with no spend; the halted Run A ledger and results
are preserved untouched as the audit record. Run B covers OpenRouter Stage 2
alone under run `zen-openrouter-live-2026-10-11-openrouter`, authorized by the
[OpenRouter-only amendment](amendment-openrouter.md): providers and credentials
are independent, no Run A spend occurred, and Run B uses separate canonical
durable files with the same reserve/halt/reconciliation guarantees. No run can
reset another run's budget, and a further run needs its own reviewed amendment.

1. Three sequential stages with halt gates: Stage 1 Zen Responses
   (one non-streaming + one streaming request, one operator-selected
   Responses-model row, text-only, `max_output_tokens` at most 128).
   Stage 2 runs only after Stage 1 success is recorded: OpenRouter Responses
   (one non-streaming + one streaming request, one operator-selected exact
   namespaced model, same text bounds). Stage 3 runs only after Stage 2
   success: OpenRouter embeddings (one call, one operator-selected exact
   embedding model, short input). Stage 3 is closed as untestable 2026-10-11:
   Zen exposes no embeddings surface and the OpenRouter catalog (458 models,
   fetched 2026-10-11) lists no embedding model, free or paid. A new upstream
   surface or catalog entry triggers a fresh amendment.
   A run manifest lists a non-empty leading prefix of the fixed case order;
   unlisted cases are never dispatched and their ledger slots stay unreserved.
   At most five live dispatches plus bounded
   read-only diagnostics; no retries, no alternative models, no production
   changes. Note: the contributor-free Zen model permits provider training on
   prompts per Zen privacy terms, so verification text stays short and
   nonsensitive per item 3.
2. Credentials are operator-supplied out of band and live only in the executing
   environment (environment variables or token-authenticated vault reads).
   They are never committed, logged, displayed, or recorded in evidence. Client
   and router keys follow the same rule. Missing/blank credentials, failed vault
   resolution and locally detectable client/admin authentication failures refuse
   before provider dispatch. Readiness cannot establish upstream key validity.
   Upstream 401/403 responses count as dispatched attempts and halt the run with
   sanitized public/provider statuses; no credential cycling or retry.
3. Requests use short nonsensitive text. Record only numeric/metadata outcomes:
   public and provider HTTP status, completion/output presence, input/output
   usage counts, local estimated debit at configured test prices, and
   admin-diagnostic reservation/inflight snapshots. Never record prompts,
   outputs, error bodies, or credential values. A bounded test-only transport
   observer captures provider status and usage before translation. Independently
   parsed upstream usage must match public usage and per-request admin credit
   deltas; public usage and settlement alone cannot prove correct mapping.
4. Streaming is verified with terminal usage and preserved SSE frame boundaries;
   there is no retry after meaningful stream output. Any ambiguous dispatched
   failure halts the entire run persistently pending review. All other failed
   acceptance checks also block subsequent cases. Use five fixed case IDs, an
   exclusive run lock and a durable ledger separate from router memory. Reserve
   each case before egress, then persist and validate its result before the next
   case, including within a stage. Missing outcomes, corrupt/mismatched state
   and write failures refuse further dispatch. Restart never resets the budget
   or replays a reserved case; there is no sixth probe or retry allowance.
   See the [execution and observation contract](activities.md).
5. Local estimated debits are computed at operator-approved test prices and are
   explicitly unrelated to provider billing. Success on one exact model says
   nothing about other models, tools/media, quota ceilings, provider admission
   traffic, Table-backed inference, or production readiness; those remain
   separately gated.

## Scope

### In scope

- Five bounded live dispatches across three gated stages plus read-only
  readiness/admin diagnostics against a dedicated test configuration.
- An isolated verification harness, durable ledger and redacted transport
  observer, with offline tests and implementation review before live use.
- Numeric-only evidence and an independent review record.

### Out of scope

- Runtime code changes (unless a real defect is established by evidence, then a
  separately reviewed amendment first).
- Additional models, tools/media/structured output, quota or admission
  characterization, Table-backed verification, cost reconciliation, and any
  production configuration or deployment change.
