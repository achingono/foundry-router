# Google AI Studio Adapter Exit Criteria

## Plan Gate

- [x] Current tree/docs/tests inspected and templates copied to this new plan directory.
- [x] Scope, owning boundaries, implementation sequence, test cases and risks documented.
- [x] Independent session reviewed the plan; findings addressed and recorded.
- [x] Relative links and final planning diff checked for unsupported claims and secrets.

## Implementation Gate

- [ ] W1 vendor assumptions confirmed; exact supported field/event matrix and ADR recorded.
- [ ] Strict Google mocks require Chat Completions `messages` and return real envelope shapes.
- [ ] Text/instructions/history translate to valid Google requests; public JSON is Responses
  shaped with logical aliases, coherent statuses/IDs, output and normalized actual usage.
- [ ] Google SSE produces ordered Responses events under fragmented/multiline/Unicode input;
  usage after finish is retained and truncation never becomes a successful completion.
- [ ] Complete/length-limited/refusal/protocol-error outcomes are distinguished and tested.
- [ ] Unsupported inputs/operations fail before reservation/egress; capable Azure candidates
  remain eligible, including during failover; Google embedding models require explicit operations.
- [ ] Embeddings preserve count/order/dimensions and use the quota store on selection,
  failover and finalization; missing usage retains estimates and non-finite vectors are rejected.
- [ ] Instructions/history enter estimates; upstream output limits match reservations.
- [ ] Repeated attempts cannot bypass quota; ambiguous dispatched attempts retain conservative
  consumption; same-project keys share budgets and cooldowns across three-or-more-key tests.
- [ ] Translation failure after billable generation settles usage/estimate; exactly-once
  credit/quota cleanup survives cancellation, store failure and upstream close failure.
- [ ] Ambiguous Google dispatch failures settle usage/estimate and never retry/fail over;
  only confirmed pre-dispatch/non-generation failures can reuse bounded retry policy.
- [ ] Google credential rejection sets backend-local cooldown; subsequent requests reach
  healthy keys and cooldown expiry behaves as documented without penalizing sibling keys.
- [ ] No retry/failover occurs after the first downstream SSE event; retry bounds, pre-output
  deadlines, resource limits and finite stream lifetime are enforced and tested.
- [ ] Google body limits apply during incremental decoded-byte reads without relying on
  `Content-Length`; the absolute reservation deadline includes retries and slow consumers.
- [ ] No credentials/prompt/output markers appear in errors/logs/metrics/admin diagnostics;
  allow-list, redirects, auth stripping and credential-query rejection regressions pass.
- [ ] Existing Azure wire behavior, non-metered opt-out, metering homogeneity and credit
  recovery invariants remain covered by passing tests.
- [ ] Focused and full suites, at least 80% coverage, lint/format/type checks, applicable
  Azurite/combined-coverage CI gates, Docker build and image smoke pass with retained evidence.
- [ ] SonarQube script run if present and all Blocker/Critical/Major findings resolved;
  independent deep review completed with actionable findings addressed.
- [ ] Canonical docs, examples and traceability match the implemented subset; relative links
  and final diff reviewed for secrets and unsupported deployment claims.

## Live Validation Gate (Separate)

- [ ] Operator supplies actual test models, credential references, project groups, limits
  and request/token/spend bounds; test app is memory/one worker/one replica.
- [ ] Bounded real non-streaming and streaming text, history and embeddings pass with usage
  settlement and safe diagnostics; evidence identifies exact models/capabilities tested.
- [ ] Test credentials/configuration follow cleanup policy; provider failure/admission traffic
  is labeled unverified unless separately tested. Production cut-over is a separate gate.

When only the implementation gate passes, report the adapter as **Implemented** with mocked
verification and real Google inference as **Planned**. Do not mark unrun live gates complete.

## Approval Table

| Role | Name | Status | Notes |
| --- | --- | --- | --- |
| Plan author | Codex | Prepared | Documentation only; no runtime implementation |
| Independent plan reviewer | `review_google_adapter_plan` session | Reviewed | Two Major findings and two Suggestions addressed; no blocking plan findings remain |
| Release approver | Project maintainer | Pending | Implementation/live rollout decisions are separate |
