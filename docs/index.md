# Foundry Router Documentation

Foundry Router is a lightweight, OpenAI-compatible proxy for Azure AI Foundry deployments. It presents multiple subscriptions or projects as one logical model endpoint, with forwarding plus health-aware retry/cooldown/failover implemented and credit-cycle/cost-aware scheduling Planned.

## Repository Status

The repository is **Partially implemented**. Configuration, authentication, health checks, model listing, backend request safety, Responses/embeddings forwarding, and health-aware retry/cooldown/failover are implemented. Credit accounting, infrastructure, and deployment remain Planned. Statements such as “must,” “should,” and “will” describe target behavior unless explicitly marked otherwise.

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

## Reading Convention

Documents in `docs/` are normative when they state a requirement or acceptance criterion. Examples are illustrative. Implementation status must use one of these labels: `Implemented`, `Partially implemented`, `Planned`, or `Design target`.
