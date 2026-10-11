# Amendment: OpenRouter-only Run B

Date: 2026-10-11. Status: proposed, pending independent review. No live
dispatches under this amendment yet.

## Background

Run A (`zen-openrouter-live-2026-10-11`, manifest `manifest.json`) halted on its
first case: Zen `muse-spark-1.3-contributor-free` returned provider 403 with no
usage and no spend. The halted Run A ledger (`ledger.json`) and results
(`results.json`) are preserved untouched as the audit record. The operator
directed skipping Zen and running OpenRouter.

## Change

Authorize Run B (`zen-openrouter-live-2026-10-11-openrouter`) covering exactly
`openrouter-nonstream` and `openrouter-stream` with the operator-approved model
`google/gemma-4-26b-a4b-it:free` at synthetic $1000/M test prices; see
[manifest.openrouter.json](manifest.openrouter.json). Zen and embeddings models
are explicitly empty in the manifest: no unapproved model may appear on record.

Run B reuses every Run A guarantee unchanged: reserve-before-egress, halt on
any failure, no retry, bidirectional ledger/results reconciliation, independent
usage observation, canonical credit-delta reconciliation at 1e-9, redacted
numeric-only evidence, and out-of-band credentials. The only delta is scope:
authorized runs and their fixed case orders live in an explicit allowlist
(`RUN_CASES`), manifests must list a non-empty leading prefix of their run's
order, and each run owns separate canonical durable files selected by the
manifest — never by operator paths. The shared stage lock serializes runs.

## Rationale

Providers, credentials, quota groups, and credit groups are independent, and
Run A spent nothing, so Run B's evidence stands on its own. Skipping the halted
Zen predecessor does not weaken any guarantee: within Run B, the streaming case
still requires its validated non-streaming pass, and any Run B failure halts
Run B. Run A cannot resume (halted ledger) and Run B cannot touch Run A
(separate files, identity-checked). A further run or any Run A revisit needs its
own reviewed amendment.

## Exit criteria delta

- [ ] Independent review of this amendment and its implementation.
- [ ] Run B manifest bound to operator-approved model/prices (committed).
- [ ] Both Run B cases pass with usage/settlement evidence and zero retained
      reservations, or the halt is recorded with no further egress.
- [ ] Embeddings remains deferred; billing, quota/admission, Table, and
      production remain gated.
