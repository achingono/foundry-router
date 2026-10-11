# Live verification evidence

**Planned.** No live dispatches made. Independent plan review is complete;
findings are addressed at the planning level. Harness implemented with offline
validation; implementation review, operator inputs, and live stages remain
pending. This record does not establish live compatibility.

| Item | Reference | Notes |
| --- | --- | --- |
| Independent plan review | [Review record](review.md) | 2026-10-11: three Major findings and one Suggestion; revised contract checked by the same reviewer and all addressed at planning level |
| Revised execution contract | [Activities](activities.md), [exit criteria](exit-criteria.md) | Five fixed cases, durable dispatch ledger, independent observation, scoped credential checks |
| Documentation validation | This documentation-only revision | Relative links resolve; whitespace and final diff checked |
| Harness ledger | `scripts/quality/zen_openrouter_live_budget.py`, `tests/unit/test_zen_openrouter_live_budget.py` | 25 offline checks: fixed five-case binding, reserve-before-egress, halt on failed/ambiguous outcomes with tamper-evident revalidation, budget cap, manifest binding |
| Harness runtime | `scripts/quality/zen_openrouter_live_runtime.py`, `tests/unit/test_zen_openrouter_live_runtime.py` | 15 offline checks with fake transports: pass paths for all five kinds, replay refusal, status/usage mismatch, missing/truncated usage, embeddings order, bound breach, secret redaction, observer-boundary rejection |
| Harness stage | `scripts/quality/zen_openrouter_live_stage.py`, `tests/unit/test_zen_openrouter_live_stage.py` | 15 offline checks: full-pass sequencing with predecessor gates, halt-on-failure, reserved-without-outcome blocking, manifest/results binding, mutation rejection, persistence-failure blocking, lock exclusivity, credential-safe CLI |
| Offline-test finding | Stage manifest binding | Offline tests showed results were not bound to the manifest and POSIX rename ignores file permissions; results now carry a manifest fingerprint and the persistence test uses a read-only directory |
| Repository verification | Repository virtual environment | 2,307 passed, 3 skipped, 19 deselected (`not docker and not azurite`); `ruff check`/`ruff format --check` clean repo-wide; strict mypy clean on `src/` |
| Static scan | Conditional repository script absent | `scripts/quality/sonarqube-scan.sh` does not exist |
| Harness implementation review | Pending | Required before live dispatch |
| Independent harness review (5 Majors) | Reviewer report, no files changed | Budget reset via path switching; truncated SSE hidden from router; exception paths misreporting dispatch; unenforced output cap; bypassed auth/readiness/admin checks |
| Finding dispositions | Harness commits on main | Canonical CLI ledger binding; unchanged byte forwarding with truncation rejection; fact harvesting on all exits plus ledger-count CLI reporting; output-cap enforcement in acceptance and result validation; real routes/auth with canonical admin evidence and setup-error propagation |
| Follow-up review (2 Majors) | Reviewer report, no files changed | Contradictory persisted success accepted on resume; SSE acceptance dependent on transport chunk boundaries |
| Follow-up dispositions | Harness commits on main | Earliest-boundary SSE split with chunking/line-ending regressions; strict resume success evidence (HTTP 200 pair, stream-mode agreement, case-specific embeddings/vector checks) |
| Follow-up verification | Reviewer report, no files changed | Both follow-up Majors verified fixed; all previously reported blocking findings resolved; 85 harness tests passed; tree and whitespace clean; full suite not rerun; no live requests sent |
| Live execution Stages 1–2 (2026-10-11) | Local-only ledger/results; numeric summary below | 1 dispatch, then persistent halt. No spend, no usage observed, no further egress |
| `zen-nonstream` | muse-spark-1.3-contributor-free | Public 403 / provider 403 in 0.329s; no usage; $0.00 debit; run halted per contract |
| Remaining Run A cases | All unreserved | `zen-stream`, `openrouter-nonstream`, `openrouter-stream` never dispatched |
| Live execution Run B (2026-10-11) | Local-only ledger/results; numeric summary below | 1 dispatch, then persistent halt. Free model, no real spend |
| `openrouter-nonstream` | google/gemma-4-26b-a4b-it:free | Public 502 / provider 200 in 1.257s; independently observed usage 7 in / 1 out, public usage absent; $0.00 debit; run halted per contract |
| `openrouter-stream` | Unreserved | Never dispatched |
| Paid-models amendment | [Amendment](amendment-paid-models.md) plus 3 committed manifests | Operator-approved: Zen gpt-5.4-mini ($0.75/$4.50), OR gpt-4o-mini ($0.15/$0.60), OR claude-haiku-4.5 ($1.00/$5.00); real list prices for local accounting; pending independent review, no live dispatches yet |
| Pending scope | Operator decision required | Zen: key reaches `/models` (41-model authed catalog) but `/responses` refuses with 403: likely workspace billing/enablement or key scope. OpenRouter: provider-200 envelope carries valid usage but fails strict translation (likely output-shape mismatch on this free model); public usage/settlement unverified. No retry, probe, or model substitution without a reviewed amendment |
| Live stages | None | No requests sent; no credentials retrieved; no production changes |
