# Foundry Router Documentation

Foundry Router is a lightweight, OpenAI-compatible proxy for Azure AI Foundry deployments. It presents multiple subscriptions or projects as one logical model endpoint, with forwarding, health-aware retry/cooldown/failover, and credit-cycle/cost-aware scheduling Implemented, and infrastructure, distributed state, and automated deployment Planned.

## Repository Status

The repository is **Partially implemented**. Configuration, authentication, health checks, model listing, backend request safety, Responses/embeddings forwarding, health-aware retry/cooldown/failover, and credit-aware scheduling are **Implemented**. Cost reconciliation loop scaffolding and stale-fallback diagnostics are **Partially implemented**. Modular decomposition, distributed state stores, metrics, and cloud infrastructure remain **Planned**. Statements such as “must,” “should,” and “will” describe target behavior unless explicitly marked otherwise.

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

## Reading Convention

Documents in `docs/` are normative when they state a requirement or acceptance criterion. Examples are illustrative. Implementation status must use one of these labels: `Implemented`, `Partially implemented`, `Planned`, or `Design target`.
