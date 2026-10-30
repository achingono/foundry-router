# Table production and autoscaling Inputs

## Status: Planned

Prepared 2026-10-30 by the disclosed Azure planner fallback after Muse failed with HTTP 402. This plan authoring session performs no implementation, Azure inspection/mutation or inference. Independent plan approval remains required.

## Required Inputs

| Input | Source | Owner |
| --- | --- | --- |
| Authorized objective | Current user instruction: validate/deploy Table-backed production, then supported Azure Foundry payloads and autoscaling; inference-cost judgement approved | Coordinator/operator |
| Workflow and ownership | [AGENTS.md](../../../AGENTS.md), [agent handoffs](../../development/agents.md), [testing](../../development/testing.md) | Coordinator |
| Canonical boundaries and contracts | [Architecture](../../architecture/index.md), [API](../../api/index.md), [configuration](../../configuration/index.md), [operations](../../operations/index.md), [shared credit](../../operations/shared-resource-credit.md) | Developer/reviewer |
| Current production baseline | [Latest production packet](../pricing-estimation-503/production-packet.md), [evidence](../pricing-estimation-503/evidence.md); refresh read-only before execution | Executor |
| Table historical acceptance and remaining gap | [Real inference](../table-real-inference/evidence.md), [write metadata](../table-write-metadata/evidence.md), [synthetic two replicas](../table-two-replica/evidence.md), [existing cross-RG](../table-existing-cross-rg/evidence.md) | Verifier |
| Distributed prerequisites | [Quota evidence](../distributed-quota-accounting/evidence.md), [metrics evidence](../metrics-aggregation/evidence.md), [observability](../../operations/observability.md) | Developer/verifier |
| Current source, tests and IaC | `src/foundry_router/api/common.py`, `credit.py`, `routing/`, `state/{azure,table,quota}.py`, provider adapters, `infra/modules/containers/router.bicep`, [IaC guide](../../../infra/README.md), relevant unit/integration tests | Developer/verifier |
| Official Azure operation limits | [Azure OpenAI Responses](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses), operation-specific embeddings/Foundry Anthropic/MAI sources and Container Apps ingress/resource/scaling documentation to collect in Phase 4 | Research owner |
| Fresh private execution material | Discovered resource identities, permissions, immutable release/source hashes, exact effective configuration/secret versions, original ingress, fresh run ID and ledger; missing historical captures do not permit replay | Executor/reviewer |
| Independent approval | Separate plan, candidate deep-review and exact executable-packet verdicts, with no unresolved Critical/Major findings | Independent reviewer |

## Baseline and scope

- Latest deployed release is `pricing-20261029`, immutable digest recorded in the linked packet; memory state, single worker and maximum one replica. Operator-observed sizing is 0.25 vCPU/0.5 GiB. Latest evidence records 22 backends, 14 pools and four canonical credit accounts. Refresh rather than assuming these observations still hold.
- Existing Table infrastructure and isolated one/two-replica synthetic checks passed. Original real nonstream failed 503 around a Table transaction 400; write-metadata sanitation corrected locally and two supplemental real streams settled successfully. Current-release real nonstream and restart acceptance are still open.
- Existing dirty `credit.py`, routing, tests, canonical docs and `docs/plans/pricing-estimation-503/` are deployed estimator USER WORK. `docs/plans/responses-request-limit/` is unrelated USER WORK. Preserve all bytes/changes; inspect and coordinate ownership before edits, never reset, overwrite or replay their packets.
- New paid acceptance is fresh authorization, not an extension of consumed historical slots. Only Azure Foundry inference is in scope, including `azure`, `azure_anthropic` and `azure_mai`. Preserve other providers' production configuration, behavior, prices, capabilities and funds; no deletion, substitution or live calls to them.
- Table migration must preserve all four accounts, including non-Azure accounts. Shared-state migration is authorized; non-Azure provider-semantic changes are not. Whole-app scale-out cannot bypass safety for preserved providers.
- Azure Responses documentation inspected for this plan says up to 50 images, each image under 512 MB, combined prompt including images under 512 MB. This is not proof of a 512 MB wire-JSON cap, an MB-to-MiB conversion, embeddings limits or a model context limit. File inputs have separate documented limits. Do not map tokens to bytes to manufacture bounds.

## Optional Inputs

- Existing collector/network/alert inventory and previous redacted benchmark results; these improve reuse but cannot replace current-release acceptance.
- Provider support clarification of unspecified wire limits; prefer authoritative sources over paid boundary probing.

## Input Validation Checklist

- [ ] Read-only live baseline, source hash manifest and effective configuration are current and agree.
- [ ] Reusable test resources and table ownership discovered before any new infrastructure proposal.
- [ ] Fresh ledger and per-case reservations prepared; old ledgers remain immutable.
- [ ] Exact packet has resolved identifiers privately, permissions, costs, bounded actions and independent approval.
- [ ] Operation limits and unresolved architecture decisions are documented, not guessed.
