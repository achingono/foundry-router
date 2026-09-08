# Phase 06 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Plan review | `docs/plans/phase-06-metrics-diagnostics/index.md` | State store & observability design review |
| ADR alignment | `docs/decisions/adr/005-state-management.md` | Azure Table Storage is the Phase 06 authoritative shared store; Redis is deferred to a separately approved optimization scope; multi-worker metrics planned for Phase 07. |
| AzureTableCreditStore | `src/foundry_router/state/table.py` (352 LOC) | Complete implementation with 8 async methods: sync_from_settings, try_assign_reservation, finalize_request, assess, apply_reconciled_remaining, live_snapshot, reset, plus internal helpers and entity serialization. Same-partition ETag transactional batch for atomic reservation lifecycle. |
| AzureTableHealthStore | `src/foundry_router/state/table.py` (165 LOC) | Complete implementation with 4 async methods: snapshot_backend_health, set_cooldown, reset. Timestamped, eventually consistent health snapshots; TTL-based cache; unconditional upserts. |
| Protocol definitions | `src/foundry_router/credit.py` (with @runtime_checkable), `src/foundry_router/health/`, `src/foundry_router/state/__init__.py` | `CreditStore` and `HealthStore` protocols with runtime conformance checks; in-memory reference implementations retained. |
| Live diagnostics | `src/foundry_router/main.py`, `/admin/status` endpoint | Authenticated access; exposes backend health, cooldown, credit state, available balance, reserved in-flight, cycle boundaries. |
| Metrics endpoint | `src/foundry_router/metrics/__init__.py`, `/metrics` endpoint | Single-process Prometheus-compatible metrics: counters, histograms, gauges; admin authentication; zero PII. Multi-process aggregation planned for Phase 07. |
| Comprehensive test suite | `tests/unit/test_state.py` (53 tests) | 40 AzureTableCreditStore tests (reservation lifecycle, atomic batch, ETag conflicts, cycle rollover, protected state, conservation, recovery); 19 AzureTableHealthStore tests (snapshots, cooldown expiry, cache invalidation, parse errors, write failures). Protocol conformance tests for both adapters. |
| Test coverage | pytest with --cov | Overall 90.94% coverage; state module 89.17% coverage (exceeds 85% requirement). |
| Type checking | mypy | Zero issues after refactoring _get_balance_locked() to use distinct variable names for cache vs. storage branches. |
| Code quality | ruff format, ruff check | Code formatted; acceptable complexity warnings (PLR0913, ARG002). |
| Verification command | `.venv/bin/python -m pytest -m "not docker" -q --cov=src/foundry_router` | 227 tests passed; no failures or blockers. |
| Git history | Latest commit | `Phase 06: Resolve mypy type checking issues in state/table.py` |
