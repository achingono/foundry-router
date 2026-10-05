# Model Alias Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Review and approve spellings confused | Wrong alias leaves actual client failing | Configure/test both independently; start validation with observed `codex-auto-review` | Open |
| R2 | Alias targets deployment/backend instead of canonical pool | Wrong routing/accounting or accidental egress | Only canonical pool targets; existing physical mapping owns deployment selection | Open |
| R3 | Requested alias used for prices/settlement | Missing prices, undercharging or duplicate balances | Canonical identity end to end, no alias price overrides, streaming/accounting tests | Open |
| R4 | Chains, collisions or default fallback obscure selection | Unintended target or loops | One-hop exact mapping, bounded validation and no unknown-name fallback | Open |
| R5 | Reviewer payload is adapted to make a target accept it | Approval semantics weakened | Change model selection only; preserve non-model fields and error outcomes | Open |
| R6 | Alias reassigned while a request/stream settles | Wrong target prices or history binding | Capture resolved identity/settings; normal drain/restart; future signed-state binding | Open |
| R7 | Response model differs from alias | Client incompatibility | Preserve raw body/SSE contract, document and test actual client acceptance | Open |
| R8 | Many aliases inflate capacity or telemetry | Admission bypass, double cost counts, cardinality growth | Shared target accounting, canonical metrics, bounded config/log fields | Open |
| R9 | Model substitution mistaken for specialized reviewer equivalence | Incorrect operational trust | Separate actual-client allow/deny/error tests; no HTTP200-as-approval inference | Open |
| R10 | Alias config lost on redeployment | Hidden model 404 returns | Optional Bicep/env plumbing and normal revision rollout documentation | Open |
| R11 | Alias bypasses later capability/continuation checks | Invalid history or target-policy evasion | Resolve first, enforce target pool rules, bind canonical target in future signed state | Open |

## Open Decisions
- Before live enablement: current target pool/deployment readiness, actual client/version/request
  parameters, response-model acceptance and bounded test scope. Historical inference is not enough.
- User-supplied upstream issues/catalog claims may be checked for troubleshooting, but are not
  prerequisites for the general one-hop routing implementation.
- Future alias chains, visibility controls, per-client permissions and model response rewriting
  need separate contracts; none is required by this plan.

Fixed decisions: explicit empty-default configuration, exact one-hop names, target policy/prices,
all configured aliases discoverable, upstream response passthrough and no review-prompt changes.
