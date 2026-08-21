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
| Configured HTTPS origin/base-path egress only | `src/foundry_router/backends/` | `tests/unit/test_backends.py` |
| Redacted failure logging and request context cleanup | `src/foundry_router/logging/`, `src/foundry_router/main.py` | `tests/unit/test_logging.py`, `tests/unit/test_main.py` |
| Reproducible package and image smoke path | `README.md`, `pyproject.toml`, `Dockerfile`, CI workflow | Phase 01 Hardening evidence |
| Combined test coverage gate | `.github/workflows/ci.yml` | CI coverage command |
