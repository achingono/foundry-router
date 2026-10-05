# Logical Model Aliases

## Companion Documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)
- [Alias contract](alias-contract.md)

## Status

**Implemented**. Local alias tests passed; subsequent ACR verification passed
482 tests with 90.38% coverage, Azurite and Docker/image smoke. The
[production rollout](../model-aliases-production/evidence.md) passed six live
Responses cases and actual Codex approval-client allow/deny/error validation.
Production remains memory/one. Exact credit continuity during the user-directed
unfenced rollout and GitHub CI remain limitations. Approval policy was unchanged;
the earlier failed push was not retried. Drafted against `333db5e` on 2026-10-05.
Independent plan review is complete with no blocking findings; see [Evidence](evidence.md).

## Objective
Allow explicit client-facing names to resolve to existing canonical model pools before provider
and deployment selection, without duplicating pools, prices or resources. Preserve request content
and existing authentication, health, quota, credit, retry and stream guarantees.

## Motivating Names and Target

The actual approval-service error named **`codex-auto-review`**. The user also requested
**`codex-auto-approve`**; that is a separately configurable custom name, not a verified alternate
name used by Codex. Both can map to the user-selected `gpt-6.1-sol` pool:

```json
{
  "codex-auto-review": "gpt-6.1-sol",
  "codex-auto-approve": "gpt-6.1-sol"
}
```

This is an opt-in example for proposed `FOUNDRY_MODEL_ALIASES_JSON`, not a built-in default.
The target must exist in loaded `FOUNDRY_MODELS_JSON`. Repository
[production evidence](../production-inference/evidence.md) records non-streaming/streaming
Responses success for `gpt-6.1-sol` through fs-swarm. It establishes neither present availability
nor equivalence to Codex's specialized approval reviewer.

Start later operational validation with the observed `codex-auto-review` mapping; other names
use the same general mechanism. An alias cannot add unsupported parameters or specialized
behavior to a target. Codex remains responsible for reviewer instructions and decisions.

## In Scope

- Optional one-hop alias-to-canonical-pool configuration, defaulting to an empty map.
- Responses (normal/streaming) and embeddings resolution before selection, estimates and
  reservation, retaining both requested and resolved identities in request context.
- Canonical accounting/policy, structured diagnostics, catalog entries and admin mappings.
- Exact preservation of non-model request fields and existing upstream response/SSE bytes.
- Optional Bicep/env wiring with no new resources; tests, docs, traceability and distinct
  code, live inference and approval-client validation gates.

## Out of Scope

- New provider deployments, discovery, wildcard/fuzzy matching, unknown-model catch-all fallback,
  alias chains, alias-specific routing/prices, or per-client ACLs.
- Changing reviewer prompts/decisions, tools, schemas, reasoning settings or Codex configuration;
  manufacturing approvals or disabling approval review.
- Response rewriting, new endpoints, hot reload, production cut-over and implementing the
  separate Google adapter/tools/multimodal plans.

## Sequence and Independence

Implement this small configuration/API-boundary feature before the broader Google work: it
addresses an observed naming failure using implemented Azure routes. No Google adapter is a
prerequisite. Future adapters consume the same resolution context and enforce the target pool's
capabilities and continuation restrictions.

## Entry Criteria

- Current config, routes, routing/settlement, catalog, diagnostics and tests inspected.
- Independent plan review completed before implementation.
- Targets/prices remain operator inputs; mocks use synthetic IDs and credentials.
- Live enablement has current target/configuration verification and bounded test scope.

## Exit Criteria

See [Exit Criteria](exit-criteria.md). Aliased inference success is not approval-review correctness.
Do not retry blocked operational actions as a side effect of this plan.

## Roles

- Owner: Runtime contributor.
- Reviewer: Independent planning session, then implementation deep review.
- Approver: Project maintainer for rollout; existing approval mechanisms still govern actions.
