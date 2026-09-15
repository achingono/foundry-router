# Foundry Router Documentation

Foundry Router is a lightweight, OpenAI-compatible proxy for Azure AI Foundry deployments. It presents multiple subscriptions or projects as one logical model endpoint, with forwarding, health-aware retry/cooldown/failover, credit-cycle/cost-aware scheduling, modular decomposition, Azure Table Storage adapters, cost reconciliation (background loop with pluggable adapter; live Azure Cost Management integration Planned), infrastructure as code, and credit-integrity hardening **Implemented**. Multi-worker metrics aggregation remains **Planned**. Redis is a separately approved future hot-state optimization only.

## Repository Status

The repository is **Implemented** through Phase 08. Configuration, authentication, health checks, model listing, backend request safety, Responses/embeddings forwarding, health-aware retry/cooldown/failover, credit-aware scheduling, modular decomposition, cost reconciliation (background loop applying externally supplied remaining-credit snapshots; see [`docs/configuration/index.md`](configuration/index.md)), Azure Table Storage state adapters, live admin diagnostics, Prometheus metrics (single-process), infrastructure (Bicep), connection-pool/HTTP/2 tuning, graceful shutdown, and CI/CD automation are **Implemented**. Multi-worker metrics aggregation via `prometheus_client` multiprocess or OpenTelemetry and optional Redis hot-state cache remain **Planned**. Statements such as “must,” “should,” and “will” describe target behavior unless explicitly marked otherwise.

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

## Reading Convention

Documents in `docs/` are normative when they state a requirement or acceptance criterion. Examples are illustrative. Implementation status must use one of these labels: `Implemented`, `Partially implemented`, `Planned`, or `Design target`.
