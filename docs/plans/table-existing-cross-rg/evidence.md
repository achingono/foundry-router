# Evidence

| Item | Reference | Notes |
|---|---|---|
| Baseline | 5f47558 | Two-replica synthetic verification committed |
| Operator choice | Current session | Dedicated hardened test account in shared RG authorized |
| Plan review | Independent session | Approved dedicated account and isolated app, shared environment settings preserved |
| Account before attachment | Azure inspection | StorageV2/Standard_LRS; shared keys false, blob public false, HTTPS true, TLS1_2, empty tags |
| Validation/what-if | Typed existing account with cross-RG scope | Validation Succeeded; no parent account writes; tables/grants target account RG; shared settings match prior deployment |
| Runtime deployment | Isolated one-replica synthetic app | Incremental deployment Succeeded; live/ready/models/admin/metrics 200 and unauthorized/cross-role 401 |
| Managed-identity operations | Replica-targeted actual adapter | 60-unit reservation created/read/released in isolated partition, without storage keys or local operator data grant |
| Restart persistence | Configured synthetic marker 76/reservation 10 | Targeted PID1 termination; restart count 1, readiness recovered, local admin and fresh Table read retained marker/reservation |
| Cleanup | Replica-targeted adapter | Estimate restored to 100, reservation released, isolated partition deleted; exec throttle Retry-After 600 respected with 610-second wait |
| Idempotency | Identical incremental redeployment | Succeeded; exactly two data grants remain, one per table, same deterministic names |
| Parent after deployment | Azure inspection | Checked hardening, kind/SKU and tags identical to before; existing module has no parent resource write |
| Baseline checks | Existing memory/two-replica apps | Both smoke suites passed after cross-RG deployment |
| Verification scope | Evidence-only increment | No runtime code changes; prior 307-pass/88.26% suite applies; real inference/provider traffic/production cut-over unverified |
| Contextual review/links | Independent session | No Critical/Major findings; current summaries reconciled; relative links and diff checks passed |
