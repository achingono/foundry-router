# Independent OpenRouter rerun review

Date: 2026-10-11.
Reviewed commits: `3322f3092a413e163dc95ab80eb5d9ac6d0d7dc6` and
`5f00cb1eba285589edd40ba349b650bb78169059`, against parent
`fe8f92b96743ed2761661aba129132142274057b`.

Scope: all ten changed files, the rerun amendment, committed manifests,
immutable model/price validation, canonical state-file selection, durable
reservation/resume and halt behavior, and the null-reasoning integration path.
The reviewing assistant independently examined the completed implementation in
this session. Only review/status documentation was edited.

## Disposition

**Independent amendment review gate cleared for the three committed rerun
manifests.** No Critical, Major or additional implementation Suggestions were
identified. Live verification remains **Planned**: these checks used fake
transports and establish no new live compatibility or provider billing evidence.
The normal credential, durable-state, acceptance and halt gates still apply.
Historical halted runs remain closed; this clearance does not permit resetting
or replaying them.

## Verified behavior

- Each new run binds to exactly one approved OpenRouter model and its configured
  input/output prices, with inactive Zen and embedding model fields empty.
  The committed manifests contain the nonstream/stream pair, output cap 128,
  timeout 120 seconds and response-byte limit 1,048,576. The existing nonempty
  leading-prefix rule still permits stopping after the first case; it cannot
  add a case or increase the two-dispatch budget. Across the three identities,
  the amendment adds at most six dispatches.
- Gemma retains the synthetic $1000/$1000 per-million test prices used to
  exercise local accounting for a free model. GPT-4o-mini retains $0.15/$0.60
  and Claude Haiku 4.5 retains $1.00/$5.00. These are configured accounting
  inputs, not measured provider charges or newly verified pricing quotations.
- Each identity maps to separate canonical ledger/results files and uses the
  existing durable initialization, stage lock, reservation and reconciliation
  paths. The diff neither renames nor resets historical identities or files.
- Independent end-to-end fake-transport probes passed both cases for each of
  the three committed manifests using null-reasoning Chat envelopes/deltas.
  Each run made exactly two transport calls, matched public/provider usage and
  local settlement, and cleared reservations. Invoking each completed run again
  made no additional calls. Synthetic historical ledger/results/identity files
  placed beside the new files remained byte-for-byte unchanged.
- A separate fake provider failure halted the first rerun after one dispatch,
  prevented its streaming case and replay, and still allowed the next independent
  run to pass its pair. The listed Gemma/OpenAI/Anthropic execution order is an
  operator procedure; the harness enforces each run's own budget and halt state.
- Eighteen independent manifest mutations (active/inactive model fields, input
  price, output price and unsupported case selection across all three identities)
  were refused before ledger creation or transport entry.

## Verification and limits

- 140 tests passed across the budget, runtime and stage unit suites,
  reasoning-tolerance unit suite and Zen/OpenRouter integration suite, using
  `.venv/bin/python -m pytest`.
- The independent probes above used temporary state directories, synthetic
  credentials and fake transports only. No actual historical live ledger was
  inspected or modified, and no live requests were sent.
- Full-suite coverage, Ruff/mypy and Docker were not rerun by this reviewer;
  implementation-reported verification is not represented as an independent run.
  The conditional SonarQube script is absent. The repository deep-review prompt
  was applied to the scoped business logic, state and trust boundaries.
- Corrected the merged rerun/probe evidence-table row, clarified the synthetic
  Gemma price and updated stale overview status text to match the recorded
  historical evidence. Plan relative links, whitespace and final diff checked.
- This review does not reopen embeddings, quota/admission, Table-backed
  inference or production gates. Earlier non-blocking reasoning-review
  Suggestions retain their separately recorded scope and disposition.
