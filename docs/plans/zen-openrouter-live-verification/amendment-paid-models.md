# Amendment: standard paid-model runs

Date: 2026-10-11. Status: proposed, pending independent review. No live
dispatches under this amendment yet.

## Background

Run A halted on Zen 403 (account/entitlement-scoped, no spend). Run B halted
on a free-model envelope failing strict translation (provider 200, public 502).
The operator directed standard paid models next: Zen GPT plus OpenRouter
OpenAI and Anthropic chat models, with real list prices for local settlement
accounting.

## Change

Three authorized runs, each a nonstream/streaming pair on one exact paid model
with its real per-million list prices:

| Run | Manifest | Model | Prices in/out per M |
| --- | --- | --- | --- |
| `...-zen-paid` | [manifest.zen-paid.json](manifest.zen-paid.json) | `gpt-5.4-mini` (Zen) | $0.75 / $4.50 |
| `...-openrouter-openai` | [manifest.or-openai.json](manifest.or-openai.json) | `openai/gpt-4o-mini` | $0.15 / $0.60 |
| `...-openrouter-anthropic` | [manifest.or-anthropic.json](manifest.or-anthropic.json) | `anthropic/claude-haiku-4.5` | $1.00 / $5.00 |

Each run owns separate canonical durable files and reuses every guarantee
unchanged (reserve-before-egress, halt on failure, reconciliation, independent
observation, redacted evidence, out-of-band credentials). Unlisted models stay
off record. Total real spend across six dispatches is a fraction of a cent at
verification token counts.

## Rationale

Standard paid models with textbook envelope shapes isolate provider-shape risk
(the Run B free-model failure) from router defects: a pass establishes the
translation path live, while Gemma/Muse diagnosis proceeds separately without
blocking standard-model evidence.

## Exit criteria delta

- [ ] Independent review of this amendment and its implementation.
- [ ] All three manifests bound to operator-approved models/prices (committed).
- [ ] Each run passes both cases with usage/settlement evidence and zero
      retained reservations, or its halt is recorded with no further egress.
- [ ] Gemma/Muse diagnosis, embeddings, billing, quota/admission, Table, and
      production remain gated.
