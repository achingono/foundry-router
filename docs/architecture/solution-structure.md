# Solution Structure

## Current Repository (Implemented through Phase 10 template; deployed multi-replica Partially implemented, Phase 11 Planned)

```text
foundry-router/
├── AGENTS.md
├── README.md
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── configuration/
│   ├── decisions/
│   ├── development/
│   ├── features/
│   ├── getting-started/
│   ├── operations/
│   ├── plans/
│   └── templates/
├── src/foundry_router/
│   ├── api/
│   ├── auth/
│   ├── backends/
│   ├── config/
│   ├── forwarding/
│   ├── health/
│   ├── logging/
│   ├── metrics/
│   ├── reconciliation/
│   ├── routing/
│   ├── credit.py
│   └── main.py
├── tests/
│   ├── unit/
│   └── integration/
├── .github/workflows/ci.yml
├── Dockerfile
└── pyproject.toml
```

Configuration, authentication, health checks, model listing, backend allow-listing, streaming/non-streaming forwarding, health cooldowns, credit-aware scheduling, Phase 05 modular decomposition, Phase 06 distributed state adapter code (`state/table.py` with `AzureTableCreditStore`/`AzureTableHealthStore`), Phase 07 `infra/` IaC plus Phase 08 credit-integrity hardening plus Phase 10 mode-parameterised Bicep (`registryMode`/`keyVaultMode`, derived image coordinates, RBAC secret wiring, ingestion cap/alert, `Basic` console-log plan, `maxReplicas: 1` interim guard) are implemented. Deployed multi-replica shared state is Partially implemented (storage provisioning, client wiring and multi-replica deployment Planned in Phase 11). Multi-worker metrics aggregation remains Planned.

## Target Structure

The modular implementation decomposes `src/foundry_router/` and adds infrastructure:

```text
foundry-router/
├── src/foundry_router/
│   ├── api/                  # FastAPI routers (openai, admin, health)
│   ├── auth/                 # API key verification & constant-time HMAC
│   ├── backends/             # Restricted HTTP client, limits, HTTP/2
│   ├── config/               # Pydantic settings & validation
│   ├── credit/               # Cycle math, reservations, estimates, scoring
│   ├── forwarding/           # Transport execution, retries, SSE parser
│   ├── health/               # Ephemeral cooldown state tracking
│   ├── logging/              # Redacted structured JSON logging
│   ├── metrics/              # Prometheus telemetry (single-process; multi-process Planned)
│   ├── reconciliation/       # Background billing cost reconciliation
│   ├── state/                # State protocols & Azure Table Storage adapters
│   └── main.py               # Lightweight lifespan & application entrypoint (graceful shutdown)
├── tests/
│   ├── unit/                 # Domain-specific unit test suites
│   ├── integration/          # End-to-end proxy and concurrency tests
│   └── fixtures/             # Mock upstream responses and SSE streams
├── infra/
│   ├── main.bicep            # Azure Container Apps environment & app
│   └── modules/              # Key Vault, Log Analytics, Storage modules
├── .github/workflows/
├── Dockerfile
└── pyproject.toml
```

Feature behavior remains strictly local to its owning boundary.
