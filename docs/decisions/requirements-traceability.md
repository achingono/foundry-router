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

## Phase 05 Modular Routing & Cost Reconciliation Traceability (Planned)

| Requirement | Target Package | Plan Reference |
| --- | --- | --- |
| Modular decomposition of `main.py` into decoupled domain packages | `src/foundry_router/{health,routing,forwarding,api}/` | `docs/plans/phase-05-routing-reconciliation/` |
| Background periodic billing reconciliation loop (`reconciliation_interval_minutes`) | `src/foundry_router/reconciliation/` | `docs/plans/phase-05-routing-reconciliation/` |
| Graceful stale-cost fallback and non-blocking background adjustments | `src/foundry_router/reconciliation/` | `docs/plans/phase-05-routing-reconciliation/` |

## Phase 06 Distributed State & Observability Traceability (Planned)

| Requirement | Target Package | Plan Reference |
| --- | --- | --- |
| `CreditStore` and `HealthStore` abstract base class / Protocol interfaces | `src/foundry_router/credit/`, `src/foundry_router/health/` | `docs/plans/phase-06-metrics-diagnostics/` |
| Distributed Redis state store adapter using atomic Lua scripts | `src/foundry_router/state/redis.py` | `docs/plans/phase-06-metrics-diagnostics/` |
| Enriched `/admin/status` live diagnostics (health cooldowns, spendable credit, reset dates) | `src/foundry_router/api/admin.py` | `docs/plans/phase-06-metrics-diagnostics/` |
| Prometheus `/metrics` and OpenTelemetry exporter | `src/foundry_router/metrics/` | `docs/plans/phase-06-metrics-diagnostics/` |

## Phase 07 Infrastructure, Connection Tuning & Operations Traceability (Planned)

| Requirement | Target Package | Plan Reference |
| --- | --- | --- |
| Bicep Infrastructure as Code for Azure Container Apps & Key Vault | `infra/` | `docs/plans/phase-07-infrastructure-operations/` |
| Outbound HTTP connection pool limits (`httpx.Limits`) and HTTP/2 multiplexing | `src/foundry_router/backends/` | `docs/plans/phase-07-infrastructure-operations/` |
| Lifespan graceful shutdown reservation and stream drain handler (`SIGTERM`) | `src/foundry_router/main.py` | `docs/plans/phase-07-infrastructure-operations/` |
| Automated CI/CD deployment pipeline and operational smoke test suite | `.github/workflows/deploy.yml`, `scripts/operations/` | `docs/plans/phase-07-infrastructure-operations/` |
