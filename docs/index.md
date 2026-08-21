# Foundry Router Documentation

Foundry Router is a planned lightweight, OpenAI-compatible proxy for Azure AI Foundry deployments. It presents multiple subscriptions or projects as one logical model endpoint, while routing by availability, quota, health, estimated cost, credit-cycle timing, and safety reserves.

## Repository Status

This repository currently contains the requirements and design baseline only. The router application, tests, infrastructure, CI workflows, container image, and deployable service have not been implemented yet. Statements such as “must,” “should,” and “will” in the documents below describe target behavior, not verified capabilities.

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

## Reading Convention

Documents in `docs/` are normative when they state a requirement or acceptance criterion. Examples are illustrative. Implementation status must use one of these labels: `Implemented`, `Partially implemented`, `Planned`, or `Design target`.
