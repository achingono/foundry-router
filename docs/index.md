# Foundry Router Documentation

Foundry Router is a lightweight, OpenAI-compatible proxy for Azure AI Foundry and Google AI Studio backends. It presents configured model pools with forwarding, health-aware retry/cooldown/failover, credit-cycle scheduling, and single-process quota-aware Google key routing. Google quota routing is **Implemented** for single-process deployments with in-memory accounting; cross-replica quota aggregation remains **Planned**. Cost reconciliation remains a background loop with a pluggable adapter; live Azure Cost Management integration is **Planned**. Redis remains a separately approved future hot-state optimization.

## Repository Status

Phase 10 Bicep existing-resource support and Phase 11 distributed-state code are **Implemented** in the repository. Phase 09 adds Google AI Studio provider support, per-project quota groups, process-local RPM/input-TPM/RPD tracking, quota-aware scoring, free-tier credit opt-out, and admin/Prometheus quota diagnostics. Azure Table provisioning, identity-only client wiring, startup selection, readiness checks, adapter hardening and Azurite tests are present, but deployed multi-replica shared state remains **Partially implemented** pending Azure validation and a two-replica deployment. Production stays memory-backed with one replica until those gates and the cut-over runbook pass. Configuration, authentication, request safety, Responses/embeddings forwarding, health-aware retry/cooldown/failover, credit-aware scheduling, existing reconciliation adapter, Bicep infrastructure, graceful shutdown, and CI/CD automation remain **Implemented** as previously documented. Statements such as “must,” “should,” and “will” describe target behavior unless explicitly marked otherwise.

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
- [Phase 10 Bicep existing-resource support plan](plans/phase-10-bicep-existing-resource-support/index.md)
- [Phase 11 distributed state wiring plan](plans/phase-11-distributed-state-wiring/index.md)

## Reading Convention

Documents in `docs/` are normative when they state a requirement or acceptance criterion. Examples are illustrative. Implementation status must use one of these labels: `Implemented`, `Partially implemented`, `Planned`, or `Design target`.
