# Evidence

| Item | Reference | Notes |
|---|---|---|
| Baseline | 649bdd1 | One-replica Table readiness and local token-adapter persistence verified |
| Plan review | Independent session | Approved distinction between isolated adapter partition and configured synthetic backend app diagnostics |
| Azure deployment | Same test image/resources; min/max 2 | Validation and reviewed what-if passed; incremental deployment Succeeded; two running ready replicas converged without manual restart |
| Replica access | Replica-targeted exec with PTY | Both replicas used deployed managed identity; quota divisor 2 verified. Azure exec throttled synchronized test with Retry-After 600; waited 610 seconds before successful retry |
| Synchronized admissions | Actual adapters on both deployed replicas | Common start time; competing 60-unit reservations against allowance 100/reserve 10 accepted exactly one; both reported inflight 60 and one live reservation |
| Configured backend diagnostics | Synthetic marker 76, reservation 10 | Ten concurrent authenticated admin responses agreed on remaining 76/inflight 10/count 1; replica-local admin and readiness also checked |
| Individual restart | Targeted SIGTERM to PID1 on one replica | Container restarted automatically, restart count 1 versus other replica 0; both running/ready. Restarted app preserved remaining 76/inflight 10/count 1; other replica retained matching diagnostics |
| Cleanup/smoke | Test state and both apps | Reservation released, estimate restored to 100, isolated partition deleted; Table and memory baseline smoke checks passed |
| Scope limitations | Operations | No inference or provider quota admission traffic; no process-local metrics aggregation claim. Existing-account cross-RG runtime and production cut-over pending |
| Code verification | Prior runtime commit | No runtime code changes; prior full suite 307 passed, 88.26% coverage retained; no repeat required for evidence-only increment |
| Contextual review/links | Independent session | No Critical/Major findings; status summaries reconciled; relative links and diff check passed |
