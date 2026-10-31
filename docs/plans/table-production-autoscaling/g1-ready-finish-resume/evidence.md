# G1 resume Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Original apply stop | Private `table-prod-g1-ready-finish-20261030-b` | Runner stopped at post-case-2 structured snapshot refusal; no case replay |
| Current isolated topology/fence | Read-only Azure CLI and public GET after stop | One active/ready current Table worker; prior revisions have zero workers; executor-only `/32` Allow; readiness 200 from the approved executor |
| Case-2 dispatch | Original e directory, append-only case-2 consumed/HTTP/observed files | HTTP 200/completed usage is private; output content is not stored |
| Case-2 settlement reconciliation | Private `case-2-reconciliation.json`, SHA-256 `63f861c42e0c10865aa50da8135f2d5f8a8fed9b7548bec03e9173cfc8067cc3` | Fresh read-only same-process Table snapshot; configured-price debit/counter delta matches; zero reservations; case 3 unstarted |
| Focused continuation tests | Repository `.venv` | 24 passed; runner-specific coverage 95% |
| Full repository tests | Repository `.venv` | 3,158 passed, 21 skipped; runtime coverage 90.46% |
| Static/type checks | Repository `.venv` | Ruff lint/format clean; Mypy clean for 77 runtime/operator source files; `git diff --check` clean |
| Contextual implementation review | [Independent implementation review](implementation-review.md) | Zero Critical/Major findings; local code review only |
| SonarQube | Script availability | `scripts/quality/sonarqube-scan.sh` is absent; no scan pass claimed |
| Reconciliation compatibility correction | Current continuation runner and focused tests | Original v1 reconciliation lacks `previous_pass_hashes`; runner now verifies prior receipts/account continuity separately and validates that field when present. No historical artifact was changed |
| Candidate verification | Repository `.venv` | Focused: 26 passed, runner coverage 94.87%; full: 3,160 passed, 21 skipped, runtime coverage 90.46%; Ruff lint/format and Mypy passed; independent diff review found no significant issues |
| Fresh continuation packet | Private `table-prod-g1-ready-finish-resume-20261030-a/prepared.json` | Read-only prepared; SHA-256 `0e8568ae705839afd7f4e920f2baed2c6e503a0349f080f45a99bc1d7a231623`; independent exact review rejected because abrupt process termination can bypass the runner's `finally` DENY |
| Live acceptance | Blocked | No approval artifact, case 3, final DENY, drain, or restart; an independently managed fail-closed watchdog is required before resubmission; executor-only `/32` Allow remains |
