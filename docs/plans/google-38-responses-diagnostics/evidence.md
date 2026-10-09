# Google 3.8 diagnostic evidence

User requested fresh diagnostics across all five projects, then explicitly requested retries.
Historical ledgers remain immutable. Independent plan review cleared bounded 15 logical cases,
45 physical attempts, 48,960 reserved tokens and zero paid spend. Retry is diagnostic-only
around the actual Responses route; production remains unchanged.

Verifier model selection and case deadline are parameterized with original defaults retained.
Safe observer records fixed errors, schema flags, timeout phases and usage maxima before
translation. Per-attempt reservations/status/waits are durable; no replay and no retry after
any streaming bytes. All 429s withhold retry. Strict result/schema checks reject unknown fields.
Independent review corrected accounting maxima, dimension overruns, terminal auth-header
retry overrides and timeout classification before execution.

21 new focused cases pass; 29 existing compatible-verifier cases passed. Ruff/format and
strict mypy pass. Full suite: 2,073 passed, 3 skipped, 19 deselected; runtime coverage 89.86%. This verifier-only change does not
alter deployed runtime and does not require another runtime Docker build. Sonar script absent.

## Initial live stage stopped

[Retained ledger](ledger.json): two physical attempts, no retries. Project-1 native low
passed HTTP 200 (7 input/1 output); compatible provider/public HTTP 200 completed text
and cleanup, but observer retained 104 versus guard/public/settlement 8 tokens. The stage
halted and every remaining case was withheld. This discrepancy does not establish a
Google billing or runtime defect: identical usage objects should yield matching counts.
Keep this ledger immutable; a same-wire numeric diagnostic is needed before correction.
