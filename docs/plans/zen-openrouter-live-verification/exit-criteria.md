# Live verification exit criteria

## Gate checklist

- [x] Independent plan review completed; findings addressed at planning level in [review](review.md).
- [ ] Harness implemented and independently reviewed; offline crash/resume, concurrency, corruption, persistence, observation and redaction checks pass.
- [ ] Applicable repository verification passes, including at least 80% coverage for implemented code.
- [ ] Exact models, prices, request bounds and five fixed cases bound to the run manifest; credentials supplied out of band.
- [ ] Durable ledger prevents replay/reset; each case passes and is persisted before the next dispatch, including within stages.
- [ ] Upstream status/usage independently observed and compared with public results; 401/403 count as dispatches and block remaining cases without credential cycling.
- [ ] Stage 1 Zen non-streaming and streaming successful with usage/output presence and zero retained reservations.
- [ ] Stage 2 OpenRouter non-streaming and streaming successful with mapped usage/settlement and zero retained reservations.
- [ ] Stage 3 OpenRouter embeddings successful with count/order/dimensions, input-token reconciliation and zero retained reservations.
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
