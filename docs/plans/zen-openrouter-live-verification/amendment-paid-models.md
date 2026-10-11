# Amendment: standard paid-model runs

Date: 2026-10-11. Status: **Planned** for live verification; the independent
paid-models amendment review gate is cleared. No live dispatches under this
amendment yet.

[Follow-up review](review-paid-models-6d5a799.md#follow-up-review-of-immutable-paid-specifications)
verified the immutable paid specifications in `0a544a0` and the pricing-evidence
correction. PM-1 and PM-2 are closed for the three committed paid manifests.
Execution prerequisites and per-run halt/settlement checks remain in force.

## Background

Run A halted on Zen 403 (account/entitlement-scoped, no spend). Run B halted
on a free-model envelope failing strict translation (provider 200, public 502).
The operator directed standard paid models next: Zen GPT plus OpenRouter
OpenAI and Anthropic chat models, with configured list-price estimates for
local settlement accounting.

## Change

Three authorized runs, each a nonstream/streaming pair on one exact paid model
with configured per-million list-price estimates for local settlement
accounting. Price sources checked October 2026: Zen pricing table at
`https://opencode.ai/docs/zen/` (fetched 2026-10-09) and the OpenRouter model
catalog at `https://openrouter.ai/api/v1/models` (fetched 2026-10-11). These
are estimates for reconciling local credit deltas, not measured provider
spend; provider billing remains explicitly unverified.

| Run | Manifest | Model | Configured $/M in/out (estimates) |
| --- | --- | --- | --- |
| `...-zen-paid` | [manifest.zen-paid.json](manifest.zen-paid.json) | `gpt-5.4-mini` (Zen) | $0.75 / $4.50 |
| `...-openrouter-openai` | [manifest.or-openai.json](manifest.or-openai.json) | `openai/gpt-4o-mini` | $0.15 / $0.60 |
| `...-openrouter-anthropic` | [manifest.or-anthropic.json](manifest.or-anthropic.json) | `anthropic/claude-haiku-4.5` | $1.00 / $5.00 |

Each run owns separate canonical durable files and reuses every guarantee
unchanged (reserve-before-egress, halt on failure, reconciliation, independent
observation, redacted evidence, out-of-band credentials). Unlisted models stay
off record. Estimated local cost across six dispatches is a fraction of a cent
at verification token counts; actual provider billing is unverified and no
spend ceiling is claimed here.

## Rationale

Standard paid models with textbook envelope shapes isolate provider-shape risk
(the Run B free-model failure) from router defects: a pass establishes the
translation path live, while Gemma/Muse diagnosis proceeds separately without
blocking standard-model evidence.

## Known limitation

Exact model/price binding applies to paid runs, where substitution could spend
a run's budget on an unapproved model. Free runs keep shape validation
(named-iff-listed models, positive finite prices) because no operator-approved
embedding model exists to complete an exact free specification, and
stage-level embeddings machinery tests require an executable embeddings case.
A hand-edited free manifest could therefore name a paid model. Mitigations:
run manifests are committed and pinned by offline tests, the CLI binds live
execution to canonical files, every dispatch is ledger-reserved with halt on
failure, and live execution always requires explicit operator credential export
per invocation. The follow-up review clears only the three paid run IDs and
committed manifests. Modified free manifests, new free ledgers and reuse/reset
of halted historical runs are outside that clearance; this amendment does not
approve using the free branch to dispatch a paid model.

## Exit criteria delta

- [x] Independent review of this amendment and its implementation recorded in the [commit review](review-paid-models-6d5a799.md).
- [x] PM-1 model/price binding fixed and independently re-reviewed in `0a544a0`; PM-2 pricing provenance/estimate wording verified.
- [x] All three committed manifests bound to their documented operator-approved model/price specifications.
- [ ] Each run passes both cases with usage/settlement evidence and zero
      retained reservations, or its halt is recorded with no further egress.
- [ ] Gemma/Muse diagnosis, embeddings, billing, quota/admission, Table, and
      production remain gated.
