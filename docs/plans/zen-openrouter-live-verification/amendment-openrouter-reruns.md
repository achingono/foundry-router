# Amendment: OpenRouter reruns against the reasoning fix

Date: 2026-10-11. Status: **Planned** live verification; independent review
gate cleared for the three committed manifests. See the
[independent review](review-openrouter-reruns-3322f30.md). No live dispatches
under this amendment yet.

## Background

Three OpenRouter runs halted with provider-200/public-502 because every
envelope carries a `reasoning` message field the strict translator rejected.
The reasoning-tolerance amendment (implemented, independently reviewed) now
accepts explicit-null `reasoning` on Chat-translated messages and deltas.
Halted ledgers stay closed; reruns require new reviewed run identities.

## Change

Three fresh run identities reusing the same approved models and prices, each a
nonstream/streaming pair with separate canonical durable files:

| Run | Manifest | Model | Configured $/M in/out (estimates) |
| --- | --- | --- | --- |
| `...-rerun-gemma` | [manifest.rerun-gemma.json](manifest.rerun-gemma.json) | `google/gemma-4-26b-a4b-it:free` | $1000 / $1000 |
| `...-rerun-openai` | [manifest.rerun-openai.json](manifest.rerun-openai.json) | `openai/gpt-4o-mini` | $0.15 / $0.60 |
| `...-rerun-anthropic` | [manifest.rerun-anthropic.json](manifest.rerun-anthropic.json) | `anthropic/claude-haiku-4.5` | $1.00 / $5.00 |

Gemma’s $1000/$1000 values are synthetic test prices for local accounting on a
free model; they are not provider prices or charges. The paid-model values are
configured estimates carried forward from the approved manifests.

All harness guarantees carry over unchanged (reserve-before-egress, halt on
failure, reconciliation, independent observation, redacted evidence, out-of-band
credentials, immutable per-run specs). Runs execute in the listed order; any
halt stops its run only — runs are independent budgets — and is recorded with
no further egress in that run.

## Rationale

The only delta since the halted runs is the reviewed translator fix targeting
the diagnosed root cause. Fresh identities preserve the halted runs as audit
records while giving each model a clean two-case budget against the fixed
code. A pass establishes OpenRouter live verification; a halt produces new
diagnostic evidence under the same contract.

## Exit criteria delta

- [x] Independent review of this amendment and its implementation.
- [x] All three rerun manifests bound to their specifications (committed).
- [x] Each rerun's nonstream case passes with usage/settlement evidence and zero
      retained reservations; stream halts recorded with no further egress.
- [ ] Streaming reruns: scope accepted as mocked-only (see exit criteria);
      not retried under this amendment.
- [ ] Billing, quota/admission, Table, and production remain gated.
