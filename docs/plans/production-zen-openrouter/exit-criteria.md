# Enablement exit criteria

## Plan and preparation gates

- [x] Independent plan review recorded; initial findings addressed at planning level.
- [ ] Operator accepts Zen-first scope and names staging/promotion/monitoring owners.
- [ ] Current baselines, exact environment deltas, tested image digest and source evidence reviewed.
- [ ] Versioned secret selection and rollback procedure proved for the actual deployment route; no silent versionless fallback.
- [ ] Existing production auth preserved, staging auth isolated, provider policy and current price provenance verified.
- [ ] Per-account budgets/quotas reviewed, staging allocation disjoint, fresh seed procedure covers existing Azure groups too.
- [ ] Reviewed maintenance/drain procedure prevents concurrent writers and revision overlap; ingress unchanged.
- [x] Immutable six-case manifests, durable identities and execution harness reviewed with offline bounds/no-replay checks.
- [x] [SV-1 state reconciliation](review-staging-harness-9a763c7.md#follow-up-review-of-08221ff) independently verified closed.
- [x] [SV-6/SV-8 final review](review-staging-harness-9a763c7.md#follow-up-review-of-82c7d09) complete; independent harness review gate cleared. Other execution gates below remain open.
- [x] Reviewer accepts [scoped public/admin deployment acceptance](amendment-black-box-acceptance.md) at plan level.
- [x] Revised evidence scope, immutable manifests and strict promotion checks implemented/reviewed; unsupported upstream claims are refused.

- [x] SE-1 code portion: [staging infrastructure amendment](amendment-staging-infrastructure.md) and both commits independently reviewed for the flat-template paths.
- [ ] SE-1 operational portion: shared-environment impact, monitoring and actual resource/grant effects established.
- [ ] SE-2: actual tested revision-to-digest binding, production configuration/secret-version packet and rollback evidence reviewed; candidate digest alone is insufficient.
- [ ] SE-3: fresh seeds for all retained Azure accounts plus Zen; shared staging allocation and production reserve policy reviewed.

- [x] [Group reserve plan review](review-group-reserves-df5396c.md) complete; revised contract cleared for local implementation only.
- [x] Group reserve independent implementation review cleared in [48012df follow-up](review-group-reserves-f891d06.md#follow-up-review-of-48012df): GI-1/GI-2 closed; startup-only configuration contract retained.
- [ ] Fresh bounded staging manifests/identities and promotion gate bind the new image/configuration; separate live execution amendment reviewed before dispatch.

- [x] [Staging roster execution design](review-roster-execution-3bd4010.md) reviewed for local harness implementation; five exact cases and staging policy specified.
- [x] Staging roster harness independently reviewed; HR-1/HR-2 and fixture suggestion addressed (`2e18d6f`, `d5d808a`).
- [x] Staging roster deployment/execution recorded with immutable release/policy binding and operator inputs; see [halted-run evidence](evidence-roster-2026-10-12.md).
- [ ] Complete roster acceptance: 5/5 required; current run halted at DeepSeek HTTP 502 after two passes. Failed-case debit/cause remain unverified; no replay or successor dispatch allowed under this identity.
- [ ] OpenRouter production expansion: resolve [OR-1/2/3](review-openrouter-roster-57bee77.md), account/policy evidence and production-execution scope; staging-only review does not clear this gate.

## Execution gates

- [ ] Staging fully ready with its preserved baseline plus exactly three new pools, canonical account inputs and correct auth.
- [x] Four original staging case records independently reviewed for completion, usage/debit and cleared reservations; see [evidence review](review-staging-evidence-be1f2c0.md). These do not validate the planned reserve-policy image.
- [ ] New-release shared-instance staging evidence independently accepted under its separately reviewed execution amendment.
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
| Independent reviewer | Plan, harness and staging case-record reviews complete; release review open | [Staging evidence review](review-staging-evidence-be1f2c0.md); SE-1 partial, SE-2 partial, SE-3 open; no production or spending approval |
| Operator / owner | Staging execution reported; release packet pending | Scope amendment, production inputs and maintenance evidence still required |
| Production approver | Pending | Concrete staging evidence and exact production release bundle |
| Monitoring / rollback owner | Pending | Alert delivery, intake halt and safe recovery procedure |
