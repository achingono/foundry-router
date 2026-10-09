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

## Same-wire numeric follow-up

[Usage diagnostic](usage-diagnostic-ledger.json) consumed one additional physical attempt
from project-1 nonstream's remaining slot allowance. Both observer and guard saw identical
bytes and numeric prompt7/completion2/total71, reasoning detail absent. Both callbacks
retained71. Public completion/cleanup passed but split settlement used9; stage remains
failed. Raw bodies, signatures and output were not stored. Three physical attempts consumed
across immutable ledgers; no retries needed to obtain these200responses.

[Aggregate usage correction](../google-compatible-usage-integrity/index.md) is now planned
to conservatively account the unattributed total excess without inventing reasoning metadata.

## Corrected all-project completion

The [usage correction](../google-compatible-usage-integrity/evidence.md) was implemented,
reviewed and verified through the actual local Responses route against Google.
[Remaining cases](remaining-ledger.json) and [stream retry completion](stream-retry-ledger.json)
preserve every attempt. See [summary](summary.json): native passed all five; corrected
nonstream passed projects 2–5; streaming passed projects 1/3/4 immediately and project 5
on its third allowed attempt. Project2 streaming exhausted three provider 503 attempts.
Project1 corrected nonstream verification returned 503 with no remaining slot attempts.
All successful compatible results validated aggregate usage, synthetic settlement and cleanup.

No new invalid-parameter errors were observed. The compatible accounting defect and Google
503 availability failures are distinct. 21 physical attempts/22,848 reserved tokens, zero paid
spend; remaining global headroom does not permit replay of exhausted logical slots. Production unchanged.
