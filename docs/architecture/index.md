# Architecture

## Objective

The target system is a small asynchronous HTTP proxy hosted on Azure Container Apps. It receives an OpenAI-compatible request, selects a configured backend, forwards the request without changing the logical model name, streams or returns the upstream response, and records health, quota, usage, and estimated cost state.

```text
Client -> OpenAI-compatible API -> Foundry Router -> configured Foundry backends
                                      |                 A / B / ...
                                      +-> cost reconciliation and telemetry
```

## Boundaries

- **API adapter (`api/`)**: Owns endpoint routing (`/openai/v1/*`, `/health/*`, `/admin/*`), request validation, authentication, protocol translation, and streaming response packaging.
- **Forwarding (`forwarding/`)**: Owns outbound HTTP transport, retry loops, bounded pre-output waiting, streaming chunk pass-through, and SSE terminal usage extraction with bounded buffers.
- **Backend client (`backends/`)**: Owns outbound connection pool lifecycle (`httpx.Limits`), keep-alive tuning, HTTP/2 multiplexing, and safe header allow-listing.
- **Routing & Scheduling (`routing/`)**: Owns candidate selection, composite scoring (ADR-006), deterministic tie-breaking, failover coordination, and explainable decision logging.
- **Health tracking (`health/`)**: Owns ephemeral health states (`ACTIVE`, `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED`), cooldown duration calculation, and snapshotting.
- **Credit subsystem (`credit/` & `reconciliation/`)**: Owns cycle calculations, conservative token/cost estimation, atomic reservation lifecycle (`try...finally`), safe-capacity validation, and periodic billing reconciliation.
- **State Store Abstraction (`state/`)**: `CreditStore` and its in-memory implementation are partially implemented. `HealthStore`, its in-memory implementation, and the injected-client Azure Table health boundary are implemented; Azure SDK integration and authoritative credit transactions remain planned. Redis remains an optional later hot-state optimization, not the authoritative store.
- **Telemetry (`logging/` & `metrics/`)**: Owns structured redacted logging, Prometheus `/metrics`, correlation IDs, and live admin diagnostics.
- **Infrastructure (`infra/`)**: Owns Bicep templates, Azure Container Apps, Key Vault secrets, managed identity RBAC, and deployment automation.

Keep these responsibilities separate. In particular, estimated local cost is not authoritative Azure cost, and model quota is not subscription credit.

## Deployment Shape

The initial target is Azure Container Apps Consumption with 0.25 vCPU, 0.5 GiB memory, and zero minimum replicas. Until the Phase 06 Azure Table Storage adapter is implemented and verified, deployments must set `max_replicas: 1`. After that prerequisite, deployments may use at most two replicas. Scale-to-zero must remain possible. Single-process deployments use in-memory credit and health state. Before multi-replica scale-out (`max_replicas > 1`) or multi-worker processes, Azure Table Storage coordinates authoritative credit balances and reservations with ETag-based conditional writes. Health and cooldown snapshots are timestamped and eventually consistent. Redis may be added later as a cache, but it does not replace the Azure Table Storage source of truth.

## Technology Direction

The preferred stack is Python 3.12+, FastAPI, asynchronous `httpx` (with HTTP/2 and connection limits), Pydantic settings, Docker, Azure Container Apps, Bicep IaC, GitHub Actions, pytest, Ruff, and mypy. These are design targets until implemented.
