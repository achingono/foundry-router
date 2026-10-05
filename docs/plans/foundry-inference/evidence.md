# Evidence

| Item | Reference | Notes |
|---|---|---|
| Authorization | Current session | Real Responses requests approved against configured test models |
| Initial matrix | Four router requests | All upstream 404; estimated debit zero; reservations cleared |
| Direct probe | One bounded v1 request | HTTP200/completed/output present, input12/output7; confirmed resource-level endpoint |
| Runtime fixes | Backend/forwarding boundaries | Responses v1 URL/no version query, selected deployment body model; embeddings unchanged. Nested terminal usage, bounded 1MiB inspection/discard recovery and observed-cost preservation after transport error |
| Independent reviews | Plan/amendments and deep review | Two pre-existing Major streaming issues found and addressed with regression coverage |
| Regression suite | Repository environment | 334 passed, 8 Azurite skipped; 87.54% coverage; Ruff/format/mypy and Docker build/health passed |
| Image/deployment | Dedicated test app only | Corrected linux/amd64 image built/pushed and incremental deployment Succeeded |
| Model 1 nonstream | Configured first deployment | HTTP200/completed/output present, input12/output7; local estimated debit0.00033; zero active/inflight |
| Model 1 stream | Configured first deployment | HTTP200, 10 events, text delta and response.completed; input12/output6; debit0.00030; no trailing partial frame or reservations |
| Model 2 nonstream | Configured second deployment | HTTP200/completed/output present, input12/output11; debit0.00045; zero active/inflight |
| Model 2 stream | Configured second deployment | HTTP200, 11 events, text delta and response.completed; input12/output8; debit0.00036; no trailing partial frame or reservations |
| Cost scope | Operator-approved test prices | Four successful router requests estimated0.00144 at $10/$30 per million, not Azure billed cost; direct probe separate |
| Pending scope | Operations | Real embeddings, provider failure/admission traffic, Table-backed real inference, cost reconciliation and production cut-over remain unverified |
| SonarQube | Required script absent | Contextual review performed; scan unavailable |
| Final contextual review | Independent session | No Critical/Major findings after fixes; exact test scope and estimates reviewed |
