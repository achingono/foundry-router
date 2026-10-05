# Production Rollout Risk Register

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Memory revision restart restores stale allowance | Credit overspend | Operator prohibited fencing; fresh snapshot minus inflight reservations pinned; later admissions/overlap not conserved | Accounting limitation |
| R2 | Placeholder/reconstructed template changes unrelated resources | Production regression | Current metadata, saved parameters, validation and what-if; narrow update if necessary | Open |
| R3 | Build differs from tested source | Untested rollout | Verified source manifest plus unique image digest | Closed |
| R4 | Reviewer HTTP success mistaken for authorization correctness | Invalid trust | Actual client allow/deny/error parsing with unchanged policy passed | Closed |
| R5 | Approval test accidentally executes a harmful action | Unintended side effect | Disposable fixtures, reserved invalid domain, exact execution markers | Closed |
| R6 | Secrets or reviewer context retained in artifacts | Data exposure | Capture secret values only in memory; print/store redacted assertions only | Open |
| R7 | Missing credentials or CI prerequisites | Deployment delay | Discover existing authorized facilities; report precise unavailable gate | Open |
