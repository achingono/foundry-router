# Solution Structure

## Current Repository (Phase 10 template and Phase 11 code implemented; deployed multi-replica Partially implemented pending Azure verification)

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
├── infra/
│   ├── main.bicep
│   ├── types/                 # Shared sealed configuration and reference contracts
│   └── modules/               # Identity, observability, scoped grants, conditional Storage
├── Dockerfile
└── pyproject.toml
```

Configuration, authentication, health checks, model listing, backend allow-listing, streaming/non-streaming forwarding, health cooldowns, credit-aware scheduling, Phase 05 modular decomposition, Phase 06 distributed state adapters, Phase 07 IaC, Phase 08 credit-integrity hardening, Phase 10 existing-resource Bicep support, and Phase 11 conditional Storage provisioning/client wiring/Azurite tests are implemented in code. Deployed multi-replica shared state remains Partially implemented pending Azure validation and a two-replica deployment. Multi-worker metrics aggregation remains Planned.

## Target Structure

Typed identity, observability, managed environment, router and new registry/vault provisioning modules are **Implemented**, along with conditional Storage and scoped access modules. The flat root retains existing-resource lookups and orchestrates dependencies. The opt-in `infra/typed.bicep` public discriminated adapter is **Implemented**, forwarding to the same root with sealed registry/vault/state contracts. [Incremental extraction evidence](../plans/bicep-module-extraction/evidence.md), [container module evidence](../plans/bicep-container-modules/evidence.md), [registry/vault evidence](../plans/bicep-registry-vault/evidence.md) and [public interface evidence](../plans/bicep-public-interface/evidence.md) record verification scope.

The modular implementation decomposes `src/foundry_router/` and adds infrastructure:

```text
foundry-router/
├── src/foundry_router/
│   ├── api/                  # FastAPI routers + adapters/ (protocol, Azure, shared compatibility translation, Google hooks)
│   ├── auth/                 # API key verification & constant-time HMAC
│   ├── backends/             # Restricted HTTP client, limits, HTTP/2
│   ├── config/               # Pydantic settings & validation (incl. supported_operations)
│   ├── credit/               # Cycle math, reservations, estimates, scoring
│   ├── forwarding/           # Transport execution, retries, SSE parser + Google translation/settlement
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

The API adapter boundary includes **Implemented** provider-neutral Responses/embeddings
and Chat Completions SSE translation in `api/adapters/openai_compatible.py`.
`GoogleAiStudioAdapter` and `GoogleStreamDecoder` supply Google feature-profile, message
and call validation hooks while native, signed and generated-audio adapters retain their
existing subclass surface. Generic bases require explicit provider hooks and a typed
request context; they perform no routing, HTTP, credential handling or state-store work.
A configurable `openai_compatible` provider is **Implemented with mocked verification** under
the [provider contract](../plans/openai-compatible-provider/index.md), with independent bounded
text hooks in `compatible_text.py`, exact-root Bearer transport and shared translated lifecycle.
`openrouter` reuses those translated text hooks and lifecycle under the
[Zen/OpenRouter contract](../plans/opencode-zen-openrouter/index.md). `opencode_zen` adds a
dedicated bounded stateless-text validator with Responses wire pass-through in `zen.py`,
single-shot dispatch independent of Azure retries, and conservative dispatched-failure
settlement. Exact upstream/model live compatibility remains **Planned**.

`state/quota.py` owns durable quota counters, bounded state, conditional admission and
settlement. `ratelimit.py` retains the store protocol, memory implementation and immutable
attempt-bound forwarding view. Routing owns candidate attempt identities; credit and
telemetry continue to use logical request IDs.

`metrics/otlp.py` owns bounded cumulative instruments, safe OTLP protobuf/transport checks
and lifespan cleanup. API routes use the live metrics proxy so opt-in startup rebinding
reaches existing route owners. Default process-local Prometheus store identity is preserved.
