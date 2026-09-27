# Foundry Router

Foundry Router is a lightweight, OpenAI-compatible proxy for Azure AI Foundry and Google AI Studio backends. It presents model pools through one OpenAI-compatible endpoint and routes requests according to backend health, project quota headroom, estimated cost, credit-cycle timing, safety reserves, and failover policy.

## Objectives

- Maximize useful utilization across multiple Azure Foundry backends.
- Route across Google AI Studio keys using shared project quota groups and explainable headroom scoring.
- Prevent either backend from being intentionally driven through its configured credit safety reserve.
- Preserve OpenAI Responses API and streaming behavior.
- Provide predictable, explainable, credit-aware routing rather than simple round-robin load balancing.
- Keep the service small, inexpensive, stateless from the HTTP request perspective, and suitable for Azure Container Apps scale-to-zero deployment.
- Provide secure credentials, observability, reconciliation with authoritative Azure cost data, infrastructure-as-code, automated delivery, and strong tests.

## Current Status

The implementation is **Implemented** through Phase 08, with Phase 09 **Partially implemented**. Google AI Studio provider support, per-project quota accounting, quota-aware selection, non-metered free-tier routing, and admin/Prometheus diagnostics are implemented in-process. Distributed quota aggregation and multi-worker metrics aggregation remain **Planned**. Existing Azure forwarding, credit-aware scheduling, state adapters, reconciliation adapter, infrastructure, graceful shutdown, and CI/CD status are described in [the documentation hub](docs/index.md).

## Development

Install the package and development dependencies with:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy src/
```

Runtime configuration is supplied through environment variables. See `.env.example` and `docs/configuration/index.md`. Do not use the synthetic values in tests or CI as production credentials.

## Documentation

- [Documentation hub](docs/index.md)
- [Getting started](docs/getting-started/index.md)
- [Architecture](docs/architecture/index.md)
- [Runtime features](docs/features/index.md)
- [Routing policy](docs/features/routing.md)
- [Public API](docs/api/index.md)
- [Configuration](docs/configuration/index.md)
- [Security](docs/configuration/security.md)
- [Development workflow](docs/development/index.md)
- [Testing strategy](docs/development/testing.md)
- [Operations and deployment](docs/operations/index.md)
- [Observability](docs/operations/observability.md)
- [Decisions and non-goals](docs/decisions/index.md)
- [Requirements traceability](docs/decisions/requirements-traceability.md)
- [Agent instructions](AGENTS.md)

## Intended Initial Scope

The first deployment is expected to route these logical models across two configured backends: `gpt-5.6-luna`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5.3-codex`, `gpt-5.2-chat`, and `text-embedding-3-large`. The design must support adding more backends and models without hard-coded A/B branching.

## Design Principle

> Treat multiple Azure Foundry subscriptions as one logical model-capacity pool while preserving each subscription's credit safety margin and maximizing utilization before each credit period ends.
