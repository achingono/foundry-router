# Watchdog Implementation Exit Criteria

## Planning gate

- [x] Independent reviewer conditionally approves this implementation plan and protocol with no unresolved Critical/Major plan findings.
- [ ] The full-host-suspension guarantee is resolved by an independently reviewed design amendment or a separately specified and verified independent data-plane enforcer; no implementation begins before that decision.
- [x] User approved all stages in principle; implementation, Azure resources and paid execution are not performed by the planning request.

## Local implementation gate

- [ ] Separate gateway/control/supervisor/verifier and fresh G1 harness satisfy [protocol](protocol.md), including peer authentication, fixed target and bounded resource use; production routing and the old continuation remain untouched.
- [ ] Runner and supervisor have distinct OS identities, inaccessible credentials and denied ptrace/descriptor/memory/token access; actual Linux subprocess bypass tests pass.
- [ ] Session, dispatch, progression, close and probe records are durable create-only, and ambiguous acknowledgements or restart cannot grant permission.
- [ ] Locked WORM retention covers at least the signed validity plus replay/forensics window; actual policy is attested and short/unverifiable retention is refused.
- [ ] Clock health, single-use heartbeat, process liveness, hard deadline, active/idle stream termination and close-versus-dispatch ordering pass race and subprocess fault injection.
- [ ] Fresh sole-writer baseline and independent per-case signed financial/identity/config snapshots are verified after slot consumption and immediately before forwarding; any drift/staleness stops.
- [ ] External Table writers, active reconciliation/reaper/ownership mutation and cycle rollover cannot intervene between snapshot and forwarding; this is proven for the current release, otherwise live dispatch is blocked for a separately reviewed amendment.
- [ ] Four distinct fresh cases are ordered and bound to signed exact body, model, budget and one-shot records; zero retries and singleton pools are independently verified and fault-tested.
- [ ] Cases form exactly two distinct Azure deployments × nonstream/stream, the actual app is Table-backed with pinned tables and scoped writer, and terminal status/usage/EOF are independently witnessed by the gateway rather than asserted by the runner.
- [ ] Cross-host aggregate allocation is bound to one session and four slots; deterministic allocation-scoped WORM slot markers prevent competing sessions/hosts dispatching the same reserve. Separate budget records remain immutable through cycle/audit and unresolved-liability closure. Pre-dispatch input/price bounds are source-proven or a separately reviewed larger reserve fits the same budget.
- [ ] The independent response witness must show HTTP 200, completed status, valid bounded usage and clean EOF; other 2xx, failed/incomplete/duplicate terminal events and malformed usage halt without advancement.
- [ ] Final DENY has separate pre/post-restart origin attestations and verifier evidence; mocks reject app/proxy 403 and missing/ambiguous logs.
- [ ] Pre-DENY pinned-origin 200, distinct consumed DENY/restart markers, diagnostic-only deadline, independently verified restart, TLS 403, calibrated details and zero upstream attempts are tested, including crashes and ambiguous mutations.
- [ ] Focused and full tests, ≥80% coverage for implemented code, Ruff/format, Mypy and applicable Docker build pass. Sonar/deep review and final diff/links/secrets checks are recorded honestly; all Critical/Major findings are addressed.

## Separate Azure and G1 gates

- [ ] Independent finite infrastructure what-if and private exact packet bind region, resources, identities, cost, network boundary and cleanup; no shared-environment fallback.
- [ ] Non-paid disposable Azure checks demonstrate dedicated isolation, effective permissions, Blob WORM/conditional-write behavior, trusted-clock bounds, forwarding expiry and calibrated ACA denial attribution.
- [ ] New exact four-case packet and fresh aggregate budget are independently reviewed and approved; prior liabilities and attempt counts are included, no old slot or result is reused, and no unsupported Azure behavior is claimed.
- [ ] Actual four-case settlement, quiet drain, both attributable DENY probes and one restart are verified before any G1 pass is claimed. No production cut-over is authorized by this plan.

## Approval Table

| Role | Status | Scope |
|---|---|---|
| Operator | Stages approved in principle | Exact Azure and paid G1 packets remain to be prepared and independently approved |
| Independent plan reviewer | Conditionally approved | No remaining Critical/Major plan findings; host-suspension decision still blocks coding |
| Implementer | Pending | Local artifacts only after plan gate |
| Verifier and implementation reviewer | Pending | Independent checks and deep review after implementation |
