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
| Live stages | None | No requests sent; no credentials retrieved; no production changes |
