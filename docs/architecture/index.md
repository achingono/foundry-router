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
- **State Store Abstraction (`state/`)**: Owns `CreditStore`/`HealthStore` protocols, in-memory stores, and injected-client Azure Table Storage adapters (`AzureTableHealthStore`, `AzureTableCreditStore`) with same-partition ETag transactions. Redis remains an optional later hot-state optimization, not the authoritative store.
- **Telemetry (`logging/` & `metrics/`)**: Owns structured redacted logging, Prometheus `/metrics` (single-process; multi-process aggregation Planned), correlation IDs, and live admin diagnostics.
- **Infrastructure (`infra/`)**: Owns Bicep templates (`infra/main.bicep`), Azure Container Apps, Key Vault secrets, managed identity RBAC, and deployment automation. **Implemented**.

Keep these responsibilities separate. In particular, estimated local cost is not authoritative Azure cost, and model quota is not subscription credit.

Shared-resource credit is **Implemented**: `credit_groups.py` owns the validated canonical account
namespace and one-pass backend alias resolution used by settings and credit stores. Memory/Table
balances, locks/caches and reservations use groups; captured ownership governs settlement. Health
continues to use deployment backend IDs. Quota groups remain independent. See
[migration](../operations/shared-resource-credit.md) and [evidence](../plans/shared-resource-credit/evidence.md).

The approved recovery amendment adds retained/durable settlement intent and conservative expiry,
fresh balance/reservation ETags, metering-aware serialized local ownership, bounded uncertain request
tracking and independently protected cleanup (`cleanup.py`). This does not create a distributed
cross-partition identity protocol; requests retain server-owned unique IDs and drained rollout rules.

## Deployment Shape

The initial target is Azure Container Apps Consumption with 0.25 vCPU, 0.5 GiB memory, and zero minimum replicas. Production remains `max_replicas: 1` until the Phase 11 Azure validation and two-replica deployment gates pass. Table adapters, an identity-only Table client, startup wiring, readiness checks and Azurite tests are implemented in code, but deployed multi-replica shared state is still **Partially implemented**. Single-process deployments use in-memory credit and health state; table mode uses Azure Table Storage for authoritative credit balances and reservations with ETag-based same-partition transactions. Health and cooldown snapshots are timestamped and eventually consistent. Redis may be added later as a cache, but it does not replace the Azure Table Storage source of truth.

## Technology Direction

The preferred stack is Python 3.12+, FastAPI, asynchronous `httpx` (with HTTP/2 and connection limits), Pydantic settings, Docker, Azure Container Apps, Bicep IaC, GitHub Actions, pytest, Ruff, and mypy. All are **Implemented** except multi-worker metrics aggregation, which remains **Planned**.
