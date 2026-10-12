# Enablement exit criteria

## Plan and preparation gates

- [x] Independent plan review recorded; initial findings addressed at planning level.
- [ ] Operator accepts Zen-first scope and names staging/promotion/monitoring owners.
- [ ] Current baselines, exact environment deltas, tested image digest and source evidence reviewed.
- [ ] Versioned secret selection and rollback procedure proved for the actual deployment route; no silent versionless fallback.
- [ ] Existing production auth preserved, staging auth isolated, provider policy and current price provenance verified.
- [ ] Per-account budgets/quotas reviewed, staging allocation disjoint, fresh seed procedure covers existing Azure groups too.
- [ ] Reviewed maintenance/drain procedure prevents concurrent writers and revision overlap; ingress unchanged.
- [ ] New immutable six-case manifests, durable identities and execution harness reviewed with offline bounds/no-replay checks before any inference.
- [ ] [Harness findings SV-1–SV-7](review-staging-harness-9a763c7.md) resolved and independently re-reviewed; staging-write/dispatch gate cleared (currently not cleared).

## Execution gates

- [ ] Staging fully ready with its preserved baseline plus exactly three new pools, canonical account inputs and correct auth.
- [ ] Four bounded staging cases pass completion, usage/debit and cleared-reservation checks; streaming completion is semantic, not HTTP-only.
- [ ] Existing monitoring detects failed/incomplete HTTP-200 streams and credit problems; named owner and stop response confirmed.
- [ ] Operator separately approves Zen-only production promotion after staging evidence review.
- [ ] Production has the tested image, reviewed versioned bundle, fresh balances and preserved baseline plus Zen; no OpenRouter entries.
- [ ] Two production Zen cases pass under the remaining durable budget before normal intake resumes.
- [ ] Retained image/topology versions and safe fresh-seed rollback procedure verified; no stale memory revision restored.
- [ ] Evidence, links and final diff complete; sensitive values kept out of repository artifacts.
- [ ] Memory/one-worker/one-replica posture, ingress and unrelated topology remain unchanged; OpenRouter production and Table/billing gates remain open.

## Approval table

| Role | Status | Scope |
| --- | --- | --- |
| Independent reviewer | Complete at plan level | [Review](review.md); no deployment or spending approval |
| Operator / owner | Pending | Revised scope, environment inputs, maintenance procedure and staging execution |
| Production approver | Pending | Concrete staging evidence and exact production release bundle |
| Monitoring / rollback owner | Pending | Alert delivery, intake halt and safe recovery procedure |
