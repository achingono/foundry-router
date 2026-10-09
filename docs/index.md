# Foundry Router Documentation

Foundry Router is a lightweight, OpenAI-compatible proxy for Azure AI Foundry and Google AI Studio backends. It presents configured model pools with forwarding, health-aware retry/cooldown/failover, credit-cycle scheduling and quota-aware routing. Opt-in [Table quota accounting](plans/distributed-quota-accounting/index.md) and [OTLP metrics aggregation](plans/metrics-aggregation/index.md) are **Implemented** locally; deployed provider admission and collector acceptance remain unverified. The [Azure Cost Management adapter](plans/azure-cost-reconciliation/index.md) is **Implemented** locally, with live billing acceptance still unverified. Redis remains a separately approved future hot-state optimization.

## Repository Status

All six production model pools passed bounded non-streaming/streaming Responses through fs-swarm, including usage-matched shared-credit settlement. Admission, settlement and observable failure-state are **Partially implemented**: verified for one pinned pool with both dispatches served by its fs-openclaw backend, including no-egress admission rejections and zero-reservation cleanup. Live upstream 429/5xx failover, remaining-pool coverage and Table-backed production cut-over remain unverified. See [production inference evidence](plans/production-inference/evidence.md) and [failure/admission evidence](plans/production-failure-admission/evidence.md).

Infrastructure and runtime code are **Implemented**. Synthetic Table one/two-replica and cross-RG verification passed. Real non-streaming/streaming Responses and usage settlement passed for both configured models in the dedicated memory/one test app. Table-backed real inference, live upstream 429/5xx failover, embeddings, authoritative cost reconciliation and production cut-over remain unverified. Production stays memory-backed with one replica. See [inference](plans/foundry-inference/evidence.md), [Table runtime](plans/table-runtime-validation/evidence.md), [two-replica](plans/table-two-replica/evidence.md) and [cross-RG](plans/table-existing-cross-rg/evidence.md) evidence for exact scope.

## Start Here

- [Project objectives and quick orientation](../README.md)
- [Getting started](getting-started/index.md)
- [Architecture and design](architecture/index.md)
- [Repository structure](architecture/solution-structure.md)

## Product Requirements

- [Runtime features](features/index.md)
- [Routing and scheduling](features/routing.md)
- [Public API](api/index.md)
- [Configuration](configuration/index.md)
- [Security](configuration/security.md)

## Engineering and Operations

- [Development workflow](development/index.md)
- [Testing strategy](development/testing.md)
- [Operations and deployment](operations/index.md)
- [Observability and troubleshooting](operations/observability.md)

## Decisions and Planning

- [Non-goals and design decisions](decisions/index.md)
- [Requirements traceability](decisions/requirements-traceability.md)
- [Planning templates](templates/)
- [Documentation baseline plan](plans/documentation-baseline/index.md)
- [Phase 03 routing plan](plans/phase-03-routing/index.md)
- [Phase 03 routing hardening plan](plans/phase-03-hardening/index.md)
- [Phase 04 credit scheduling plan](plans/phase-04-credit-scheduling/index.md)
- [Phase 04 credit hardening plan](plans/phase-04-hardening/index.md)
- [Phase 05 modular routing & cost reconciliation plan](plans/phase-05-routing-reconciliation/index.md)
- [Phase 06 state store abstractions & metrics plan](plans/phase-06-metrics-diagnostics/index.md)
- [Phase 07 infrastructure & operations plan](plans/phase-07-infrastructure-operations/index.md)
- [Phase 08 credit-integrity and boundary hardening plan](plans/phase-08-credit-integrity-hardening/index.md)
- [Phase 09 Google AI Studio multi-key quota-aware routing plan](plans/phase-09-google-ai-studio-multikey/index.md)
- [Google AI Studio capacity inventory (Partially implemented; selected quotas measured, remaining quotas pending)](plans/google-ai-studio-capacity-inventory/index.md)
- [Google AI Studio backends and Responses adapter plan (Implemented locally)](plans/google-ai-studio-adapter/index.md); [scoped compatible text live evidence](plans/google-compatible-signature-text/evidence.md)
- [OpenCode Zen and OpenRouter backends plan (Implemented locally; live gates Planned)](plans/opencode-zen-openrouter/index.md)- [Google AI Studio tools and multimodal follow-up plan (Partially implemented; unsigned tools/structured text/small PNG, live gate Planned)](plans/google-ai-studio-tools-multimodal/index.md)
- [Logical model aliases plan (Planned)](plans/model-aliases/index.md)
- [Phase 10 Bicep existing-resource support plan](plans/phase-10-bicep-existing-resource-support/index.md)
- [Phase 11 distributed state wiring plan](plans/phase-11-distributed-state-wiring/index.md)
- [Memory-mode Azure validation and baseline deployment](plans/memory-mode-validation/index.md)
- [Bicep typing foundation](plans/bicep-typing/index.md)
- [Incremental Bicep module extraction](plans/bicep-module-extraction/index.md)
- [Typed Container Apps modules](plans/bicep-container-modules/index.md)
- [Typed registry and vault provisioning](plans/bicep-registry-vault/index.md)
- [Public typed deployment interface](plans/bicep-public-interface/index.md)
- [Table runtime validation](plans/table-runtime-validation/index.md)
- [Two-replica synthetic Table verification](plans/table-two-replica/index.md)
- [Existing-account cross-RG Table verification](plans/table-existing-cross-rg/index.md)
- [Real Foundry test backend configuration](plans/foundry-test-backend/index.md)
- [Real Foundry inference verification](plans/foundry-inference/index.md)
- [Production Foundry configuration](plans/production-foundry/index.md)
- [Production inference verification](plans/production-inference/index.md)
- [Production failure/admission verification (Partially implemented; one pool, live failover unverified)](plans/production-failure-admission/index.md)
- [Shared resource credit accounting](plans/shared-resource-credit/index.md)

## Reading Convention

Documents in `docs/` are normative when they state a requirement or acceptance criterion. Examples are illustrative. Implementation status must use one of these labels: `Implemented`, `Partially implemented`, `Planned`, or `Design target`.
