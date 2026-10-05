# Requirements Traceability

The original monolithic requirements document was split into the following destinations. This table is the audit map for sections 1–49.

| Source sections | Destination |
| --- | --- |
| 1–3, 49 | [index](../index.md), [decisions](index.md) |
| 4–5, 27, 40 | [architecture](../architecture/index.md), [operations](../operations/index.md) |
| 6–9, 24 | [API](../api/index.md), [configuration](../configuration/index.md) |
| 10–16, 18–20, 32, 33–36, 43–45 | [routing](../features/routing.md), [configuration](../configuration/index.md) |
| 17, 22–23 | [observability](../operations/observability.md) |
| 21 | [operations](../operations/index.md) |
| 25, 38 | [security](../configuration/security.md) |
| 26, 28 | [operations](../operations/index.md), [development](../development/index.md) |
| 29 | [solution structure](../architecture/solution-structure.md) |
| 30 | [configuration](../configuration/index.md) |
| 31 | [operations](../operations/index.md), [API](../api/index.md) |
| 37 | [testing](../development/testing.md) |
| 39 | [testing](../development/testing.md) |
| 41–42 | [decisions](index.md), [routing](../features/routing.md) |
| 46 | [README](../../README.md), [getting started](../getting-started/index.md), and all topic guides |
| 47–48 | [AGENTS.md](../../AGENTS.md), [development](../development/index.md), [testing](../development/testing.md) |

The rewritten documents preserve the safety-critical requirements: credit versus quota separation, per-backend cycles, reserves, concurrency reservations, bounded failover, no retry after streaming begins, configured-backend-only egress, stale-cost handling, and explicit implementation-status labeling.

## Shared Resource Credit Traceability (Implemented runtime)

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Safe canonical credit namespace; optional backend-default groups and canonical Settings keys | `src/foundry_router/credit_groups.py`, `config/` | `tests/unit/test_shared_resource_credit.py` |
| Combined cross-model capacity, group cycles/reservations, immutable ownership and legacy defaults | `credit.py`, `state/table.py` | Shared-credit unit tests; Azurite cross-model contention/settlement/restart test |
| Typed finalization failure; no second egress after failed release; independent quota/telemetry cleanup | `routing/`, `forwarding/`, `api/common.py` | Failover, cancellation, streaming and settlement-failure regressions |
| Unique routable-group readiness, canonical admin/metric views and reconciliation counts | `api/routes/`, `metrics/`, `reconciliation/`, `main.py` | Shared-credit diagnostics/readiness/reconciliation tests |
| Drained writers and explicit starting estimates; no implicit partition sum/migration | [operations](../operations/shared-resource-credit.md) | [verification evidence](../plans/shared-resource-credit/evidence.md) |
| Twelve deployments/six pools/two production credits without placeholder deployment | Implemented (production configuration) | [Production evidence](../plans/production-foundry/evidence.md); readiness/topology verified, production inference pending |
| Independent-review financial recovery: conservative legacy expiry, durable intent and dual ETag settlement | `credit.py`, `state/table.py`, `state/azure.py` | `tests/unit/test_credit_recovery.py`; real Azurite intent/recovery race |
| Ambiguous admission hard-stop, metering-aware serialized publication and bounded same-ID ownership | `credit.py`, `state/table.py` | Commit-then-timeout/no-egress, metering-flip, interleaving, incomplete discovery and ownership-limit fault tests |
| Context close cannot suppress financial cleanup; repeated cancellation and bounded timeout join | `cleanup.py`, `forwarding/` | Close-error, repeated-cancel, timeout and non-cooperative bounded-tracking fault tests |
| Failed membership sync blocks new-settings egress; same-object retry | `state/table.py`, routing typed-error boundary | `tests/unit/test_credit_follow_up.py`; real Azurite failed-sync/retry regression |
| Periodic complete ownership discovery retires absent/finalized slots independently of provider availability | `state/table.py`, `reconciliation/` | No-commit timeout, external reaper, lost acknowledgement and incomplete/ambiguous cap regressions; real Azurite |
| Post-output failed streams charge known usage or full reserve, never status-based zero intent | `forwarding/` | Memory/Table known/no-usage/zero-usage regressions; real Azurite full-reserve debit; corrected existing main test |

## Implemented Hardening Traceability

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Strict configuration shape and secret validation | `src/foundry_router/config/` | `tests/unit/test_config.py` |
| Configured per-backend HTTPS origin/base-path egress only | `src/foundry_router/backends/` | `tests/unit/test_backends.py` |
| Redacted failure logging and request context cleanup | `src/foundry_router/logging/`, `src/foundry_router/main.py` | `tests/unit/test_logging.py`, `tests/unit/test_main.py` |
| Reproducible package and image smoke path | `README.md`, `pyproject.toml`, `Dockerfile`, CI workflow | Phase 01 Hardening evidence |
| Combined test coverage gate | `.github/workflows/ci.yml` | CI coverage command |

## Phase 02 Forwarding Traceability

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Authenticated Responses and embeddings forwarding | `src/foundry_router/main.py`, `src/foundry_router/backends/` | `tests/unit/test_main.py` |
| Unknown-model and malformed-request rejection before egress | `src/foundry_router/main.py` | `tests/unit/test_main.py`, `tests/integration/test_full_flow.py` |
| Deployment URL/API-version construction and backend credential isolation | `src/foundry_router/config/`, `src/foundry_router/backends/` | `tests/unit/test_main.py`, `tests/unit/test_backends.py` |
| Streaming pass-through without retry/failover, including pre-output failure handling | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Required deployments, deterministic tie-breaking, strict embeddings input, and correlation propagation | `src/foundry_router/config/`, `src/foundry_router/main.py` | `tests/unit/test_config.py`, `tests/unit/test_main.py` |

## Phase 03 Routing Traceability

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Retryable failure classification (429/5xx/transport), bounded retries, and exponential backoff with `Retry-After` parsing | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Backend health state tracking (`ACTIVE`, `QUOTA_COOLDOWN`, `ERROR_COOLDOWN`, `DISABLED`) with `asyncio.Lock` protection | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Cooldown-aware backend filtering and single failover to next candidate | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Exhausted-cooldown response (`429`/`503`) with minimum remaining `Retry-After` | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Streaming contract preservation: retry/failover only before first chunk; post-start failures emitted as SSE error events | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Safe upstream response-header propagation and stream context cleanup | `src/foundry_router/main.py` | `tests/unit/test_main.py` |

## Phase 04 Credit Scheduling Traceability

| Requirement | Implementation | Evidence |
| --- | --- | --- |
| Local per-request cost estimation for Responses and embeddings with pricing fail-closed behavior | `src/foundry_router/credit.py`, `src/foundry_router/main.py` | `tests/unit/test_main.py`, `tests/unit/test_credit.py` |
| UTC cycle-window handling and local backend estimate initialization | `src/foundry_router/credit.py`, `src/foundry_router/config/__init__.py` | `tests/unit/test_config.py`, `tests/unit/test_main.py`, `tests/unit/test_credit.py` |
| In-memory request reservation lifecycle with guaranteed release via `try...finally` | `src/foundry_router/credit.py`, `src/foundry_router/main.py` | `tests/unit/test_main.py`, `tests/unit/test_credit.py` |
| Non-2xx response zero-charge release (releasing reservation without debiting backend) | `src/foundry_router/main.py` | `tests/unit/test_main.py` (`test_non_2xx_response_releases_reservation_without_charge`) |
| Streaming terminal SSE `usage` parsing for exact cost finalization | `src/foundry_router/main.py` | `tests/unit/test_main.py` (`test_stream_response_uses_terminal_usage_to_finalize_charge`) |
| Safe-capacity rejection without backend egress (`insufficient_credit_capacity`) | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Credit-aware candidate scoring layered after health/cooldown filtering | `src/foundry_router/credit.py`, `src/foundry_router/main.py` | `tests/unit/test_main.py`, `tests/unit/test_credit.py` |
| Explainable routing structured decision logging (`routing_decision` event) | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Dedicated unit test suite with >= 90% coverage for `credit.py` | `tests/unit/test_credit.py` | `tests/unit/test_credit.py` (91.07% module coverage) |

## Phase 05 Modular Routing & Cost Reconciliation Traceability (Implemented)

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- |
| Modular decomposition of `main.py` into decoupled domain packages | Implemented | `src/foundry_router/{health,routing,forwarding,api}/`, `src/foundry_router/main.py` | `tests/unit/test_main.py`, `docs/plans/phase-05-routing-reconciliation/` |
| Background periodic billing reconciliation loop applying externally supplied remaining-credit snapshots (`reconciliation_interval_minutes`) | Partially implemented — loop and adapter interface are implemented; only a settings-based override adapter exists, live Azure Cost Management integration is Planned | `src/foundry_router/reconciliation/`, `src/foundry_router/main.py`, `src/foundry_router/credit.py` | `tests/unit/test_reconciliation.py`, `tests/unit/test_credit.py` |
| Graceful stale-cost fallback and non-blocking background adjustments | Implemented | `src/foundry_router/reconciliation/`, `src/foundry_router/main.py` | `tests/unit/test_reconciliation.py` |

## Phase 06 Distributed State & Observability Traceability (Implemented)

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- | --- |
| `CreditStore` protocol interface with swappable implementation boundary | Implemented | `src/foundry_router/credit.py` | `tests/unit/test_credit.py`, `tests/unit/test_state.py` (protocol conformance tests) |
| `HealthStore` protocol with in-memory implementation and Azure Table adapter | Implemented | `src/foundry_router/health/`, `src/foundry_router/state/table.py` | `tests/unit/test_state.py` (19 health store tests, 96.25% coverage) |
| Azure Table Storage authoritative credit and reservation adapter using same-partition ETag transactional batch | Implemented (adapter, identity-only client, conditional provisioning/wiring and tests); deployed multi-replica shared state Partially implemented pending Azure validation and two-replica deployment | `src/foundry_router/state/table.py`, `src/foundry_router/state/azure.py`, `infra/main.bicep` | `tests/unit/test_state.py`, `tests/unit/test_table_concurrency.py`, `tests/integration/test_azurite_distributed_state.py` |
| Optional Redis hot-state cache after a concrete latency requirement and separate approval | Planned | Future scope | `docs/decisions/adr/005-state-management.md` |
| Enriched `/admin/status` live diagnostics (health cooldowns, spendable credit, reset dates) | Implemented | `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Prometheus `/metrics` exporter (single-process in-process collection) | Implemented | `src/foundry_router/metrics/`, `src/foundry_router/main.py` | `tests/unit/test_main.py` |
| Multi-process metric aggregation (`prometheus_client` multiprocess or OpenTelemetry) | Planned for Phase 07 | `src/foundry_router/metrics/` | `docs/plans/phase-06-metrics-diagnostics/`, `docs/operations/observability.md` |

## Phase 07 Infrastructure, Connection Tuning & Operations Traceability (Implemented)

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- | --- |
| Bicep Infrastructure as Code for Azure Container Apps & Key Vault | Implemented | `infra/main.bicep`, `infra/parameters.*.json` | `infra/README.md` (deployment guide, 200+ LOC Bicep with Log Analytics, Key Vault, container app config) |
| Outbound HTTP connection pool limits (`httpx.Limits`) and HTTP/2 multiplexing | Implemented | `src/foundry_router/backends/__init__.py`, `src/foundry_router/config/__init__.py` | Settings fields (http_max_connections, http_max_keepalive_connections, http_keepalive_expiry_seconds, http2_enabled); AllowedBackendClient integration; all 227 tests passing |
| Lifespan graceful shutdown with request draining (`SIGTERM` timeout) | Implemented | `src/foundry_router/main.py` | `_active_requests` counter, `track_active_requests` middleware, `_drain_active_requests()` with timeout, integrated into lifespan context |
| Automated CI/CD deployment pipeline and operational smoke test suite | Implemented | `.github/workflows/deploy.yml`, `scripts/operations/smoke-test.sh` | GitHub Actions multi-stage workflow (build, validate, deploy staging, smoke tests); bash smoke test with retry logic and admin diagnostics validation |

## Phase 08 Credit-Integrity and Boundary Hardening Traceability (Implemented)

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- | --- |
| Server-owned reservation/finalization identity decoupled from client `x-request-id` (F1) | Implemented | `src/foundry_router/main.py`, `src/foundry_router/api/routes/openai.py` | `tests/unit/test_main.py` (`test_duplicate_client_request_id_creates_independent_reservations`) |
| Bounded request intake: `413` before JSON parsing, bounded token-estimation recursion (F2) | Implemented | `src/foundry_router/api/common.py`, `src/foundry_router/config/__init__.py`, `src/foundry_router/credit.py` | `tests/unit/test_api_common.py`, `tests/unit/test_credit.py` |
| Credit/pricing configuration completeness surfaced at readiness rather than a silent permanent 503 (F3) | Implemented | `src/foundry_router/api/routes/health.py` | `tests/unit/test_main.py` (readiness tests) |
| Reservation age tracking, bounded reaper, and admin visibility of reservation count/age (F4) | Implemented | `src/foundry_router/credit.py`, `src/foundry_router/api/routes/admin.py`, `src/foundry_router/config/__init__.py` | `tests/unit/test_credit.py` (reaper tests) |
| `parse_retry_after` hardened against non-ASCII digit headers (F5) | Implemented | `src/foundry_router/forwarding/__init__.py` | `tests/unit/test_main.py` (`test_retry_after_non_ascii_digit_returns_none`) |
| Streaming usage extraction pre-filter with unchanged charged-cost semantics (F7) | Implemented | `src/foundry_router/forwarding/__init__.py` | `tests/unit/test_main.py` (terminal usage tests) |
| Constant-work auth key comparison without early return (F8) | Implemented | `src/foundry_router/auth/__init__.py` | `tests/unit/test_auth.py` |
| Per-request `sync_from_settings` retained for correctness; made cheap via settings-identity fast path (F6, revised) | Implemented | `src/foundry_router/routing/__init__.py`, `src/foundry_router/credit.py` | `tests/unit/test_credit.py`, `tests/unit/test_main.py` |

F3 was implemented as a `/health/ready` diagnostic rather than a fail-fast config-load error: hard-failing config load on incomplete per-backend credit configuration or per-model pricing would have made the existing request-time fail-closed defense (`insufficient_credit_capacity`) unreachable and would have broken legitimate partial-configuration scenarios exercised by the existing test suite (see [risk register](../plans/phase-08-credit-integrity-hardening/risk-register.md)). F6 was implemented by retaining the per-request `sync_from_settings` call — removing it broke correctness for any caller that swaps the `Settings` singleton without a corresponding explicit sync — and instead adding a settings-object-identity fast path so repeated calls with the same (`lru_cache`d) settings instance are effectively free in production.

## Phase 09 Google AI Studio Multi-Key Quota Routing (Implemented; single-process scope)

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- | --- |
| Provider-specific Google OpenAI-compatible URL and API-key header with client-header stripping | Implemented | `src/foundry_router/config/`, `src/foundry_router/backends/` | `tests/unit/test_config.py`, `tests/unit/test_backends.py`; vendor references in ADR-007 |
| One backend per key and project-scoped quota-group configuration, including unknown-group rejection | Implemented | `src/foundry_router/config/` | `tests/unit/test_config.py`, `tests/unit/test_main.py` |
| Monotonic 60-second RPM/input-TPM, Pacific-midnight RPD, bounded reservations and actual-token reconciliation | Implemented (in-memory single process) | `src/foundry_router/ratelimit.py`, `src/foundry_router/api/common.py`, `src/foundry_router/forwarding/` | `tests/unit/test_ratelimit.py`, `tests/unit/test_main.py` |
| Quota-headroom score, candidate filtering, project-wide proactive and reactive cooldown | Implemented | `src/foundry_router/routing/`, `src/foundry_router/forwarding/`, `src/foundry_router/credit.py` | `tests/unit/test_main.py`, `tests/unit/test_credit.py` |
| Homogeneous non-metered free-tier credit opt-out and zero pricing for free model pools | Implemented | `src/foundry_router/config/`, `src/foundry_router/api/routes/health.py`, `src/foundry_router/routing/` | `tests/unit/test_main.py`, `tests/unit/test_config.py` |
| Per-key/group quota diagnostics and budget/cooldown metrics | Implemented | `src/foundry_router/api/routes/admin.py`, `src/foundry_router/metrics/` | `tests/unit/test_main.py`, `tests/unit/test_metrics.py` |
| Cross-replica quota consistency and multi-worker quota/metrics aggregation | Planned | Future distributed rate-limit store | Phase 09 plan; no distributed quota adapter is implemented |

## Phase 10 Bicep Existing-Resource Support Traceability (Implemented as template code)

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- | --- |
| Mode-parameterised registry/vault (`new`/`existing`), derived image coordinates, external `registryServer`, no free-text image reference | Implemented | `infra/main.bicep`, `infra/bicepconfig.json`, `infra/modules/` | Build/lint pass with remaining BCP036 warning; BCP037 field removed after Azure rejection; `infra/parameters.example.json` |
| Registry pull + vault secret wiring with least-privilege role assignments and cross-RG modules | Implemented | `infra/main.bicep`, `infra/modules/registryPullRole.bicep`, `infra/modules/vaultSecretsRole.bicep` | Template + `infra/README.md` (first-deploy convergence, deployer permissions) |
| Name validation, daily ingestion cap + 90% alert, Analytics Classic console-log plan, source-volume reduction | Implemented | `infra/main.bicep`, `Dockerfile`, `src/foundry_router/routing/` | `tests/unit/test_routing_log_volume.py`; `infra/README.md`; Azure rejected Basic on the Classic table |
| Basic console-log plan through DCR-based ingestion migration | Planned | Current ACA integration is Classic and supports Analytics | Separate migration required; not deployed |
| Memory-mode conditional storage isolation and synthetic baseline smoke deployment | Implemented | `infra/modules/storageAccountResources.bicep`, `infra/main.bicep` | [Validation evidence](../plans/memory-mode-validation/evidence.md); real inference and Table runtime remain unverified |
| Exported Bicep mode aliases and sealed internal module contracts with compatible flat root API | Implemented | `infra/types/`, `infra/modules/`, `infra/main.bicep` | [Typing evidence](../plans/bicep-typing/evidence.md); compiler rejection checks, semantic ARM comparison and synthetic redeployment |
| Typed identity and observability resource modules | Implemented | `infra/modules/identity.bicep`, `infra/modules/observability.bicep` | [Extraction evidence](../plans/bicep-module-extraction/evidence.md); resource settings/GUIDs preserved, no credential outputs, synthetic redeployment verified |
| Typed Container Apps environment/router modules with secure password and explicit secret references | Implemented | `infra/modules/containers/`, `infra/types/containers.bicep` | [Container module evidence](../plans/bicep-container-modules/evidence.md); exact ACA payload/dependency equivalence and synthetic redeployment |
| Typed new registry/vault provisioning and resource-scoped grants | Implemented | `infra/modules/registry.bicep`, `infra/modules/key-vault.bicep`, `infra/types/resources.bicep` | [Registry/vault evidence](../plans/bicep-registry-vault/evidence.md); all four mode validations; existing/existing synthetic deployment verified |
| Opt-in public discriminated registry/vault/state interface with secure password and flat CI compatibility | Implemented | `infra/typed.bicep`, `infra/types/deployment.bicep` | [Public interface evidence](../plans/bicep-public-interface/evidence.md); branch schema rejection, parameter/output mapping and typed synthetic redeployment |
| Interim `maxReplicas: 1` guard with explicit single-revision mode and documented rollout overlap | Implemented | `infra/main.bicep`, `infra/parameters.*.json` | `infra/README.md`; deployed multi-replica shared state Partially implemented, Phase 11 Partially implemented |
| Backend/model/pricing/cycle topology wired via Key Vault secret references (`FOUNDRY_BACKENDS_JSON`, `FOUNDRY_MODELS_JSON`, `FOUNDRY_PRICING_JSON`, cycle/allowance/remaining) | Implemented (template code) | `infra/main.bicep` | Deep-review remediation; secret values remain operator-supplied out of band |

## Phase 11 Distributed State Wiring Traceability (Partially implemented)

Production model configuration and cross-subscription registry pull are **Implemented** and verified by [production configuration evidence](../plans/production-foundry/evidence.md): six selected pools, 12 backend deployments and two canonical credit groups; memory/one replica. Production inference and Table cut-over remain pending.

Azure Responses v1 deployment substitution, bounded SSE usage inspection and nested terminal usage settlement are **Implemented** and verified by [real inference evidence](../plans/foundry-inference/evidence.md). Embeddings remains deployment-scoped; real embeddings and provider failure traffic remain unverified.

| Requirement | Implementation Status | Package | Evidence |
| --- | --- | --- | --- |
| Conditional Azure Table provisioning, identity-only client wiring, `memory`/`table` state-backend validation | Implemented (template + settings code) | `infra/main.bicep`, `src/foundry_router/config/`, `src/foundry_router/state/azure.py` | `tests/unit/test_distributed_wiring.py`, `tests/unit/test_config.py` |
| Table health/credit adapters with create-if-absent sync, ETag-guarded transactions, recompute-on-conflict | Implemented | `src/foundry_router/state/table.py` | `tests/unit/test_table_concurrency.py`, `tests/unit/test_table_client.py` |
| Failover releases first-backend reservation before second selection (no cross-partition orphan) | Implemented | `src/foundry_router/routing/` | Deep-review Finding 1; `tests/unit/test_main.py` failover tests |
| `finalize_request(backend_id=None)` scans configured partitions (not only TTL cache) | Implemented | `src/foundry_router/state/table.py` | Deep-review Finding 6 |
| Google payload substitutes `config.deployment` for logical model; `responses` maps to Google-supported `chat/completions` | Implemented | `src/foundry_router/backends/` | Deep-review Finding 3; `tests/unit/test_backends.py` |
| Azurite integration + unit collection without optional `azure` extra | Implemented | `tests/integration/azurite_fixtures.py`, `tests/unit/test_table_client.py` | `pytest -m "not azurite"` collection clean; azurite-marked tests skip without emulator |
| Rate-limit replica share wiring and per-replica effective limits | Implemented | `src/foundry_router/ratelimit.py`, `src/foundry_router/routing/` | `tests/unit/test_distributed_wiring.py` |
| Azure template validation and one-replica synthetic Table runtime | Implemented | `infra/`, `pyproject.toml`, state adapters | [Table runtime evidence](../plans/table-runtime-validation/evidence.md); token-only readiness and restart persistence verified |
| Two-replica synthetic deployment and individual container restart persistence | Implemented | Isolated Table test app | [Two-replica evidence](../plans/table-two-replica/evidence.md); real inference/provider admission traffic not tested |
| Existing-account cross-RG synthetic runtime | Implemented | Existing-account module and isolated test app | [Cross-RG evidence](../plans/table-existing-cross-rg/evidence.md); scoped token access, redeployment and restart persistence |
| Production cut-over | Planned | `infra/`, operations | Reconciled starting balances, real traffic verification and explicit cut-over runbook remain pending; production memory/one |
| Multi-worker metrics aggregation via multiprocess mode or OpenTelemetry | Planned | `src/foundry_router/metrics/` | Single-process Prometheus implemented; multiprocess planned |
