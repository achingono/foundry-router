# Live verification exit criteria

## Gate checklist

- [x] Independent plan review completed; findings addressed at planning level in [review](review.md).
- [x] Harness implemented with offline crash/resume, concurrency, corruption, persistence, observation and redaction checks passing.
- [ ] Harness independently reviewed.
- [ ] Applicable repository verification passes, including at least 80% coverage for implemented code.
- [x] Exact models, prices, request bounds and listed cases bound to the run manifest ([manifest.json](manifest.json), Stages 1–2).
- [ ] Credentials supplied out of band at execution time.
- [ ] Durable ledger prevents replay/reset; each case passes and is persisted before the next dispatch, including within stages.
- [ ] Upstream status/usage independently observed and compared with public results; 401/403 count as dispatches and block remaining cases without credential cycling.
- [x] Stage 1 Zen non-streaming and streaming successful with usage/output presence and zero retained reservations (paid `gpt-5.4-mini` run).
- [x] Stage 2 OpenRouter non-streaming successful with mapped usage/settlement and zero retained reservations (three models).
- [ ] Stage 2 OpenRouter streaming: accepted scope limitation 2026-10-11. Non-streaming is established live; streaming stays covered by mocked verification only, given observed provider terminator variability. Reopens via fresh amendment, not by rerunning halted ledgers.
- [ ] Stage 3 OpenRouter embeddings: closed as untestable 2026-10-11 (no Zen embeddings surface; OpenRouter catalog of 458 models lists none, free or paid). Reopens only on a new upstream surface or catalog entry via fresh amendment.
- [ ] Per-request canonical credit-group deltas reconciled against independently observed usage at test prices; explicitly unrelated to provider billing.
- [ ] Evidence/review/links complete; no prompts, outputs, error bodies, or credential values recorded.
- [ ] Pending gates (other models, billing, quota/admission, Table, production) explicit.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Owner | | Pending | |
| Reviewer | Reviewing assistant in this session | Plan findings resolved | [Review record](review.md); harness/live reviews pending |
| Approver | | Pending | |

Five bounded dispatches do not establish general upstream support.
