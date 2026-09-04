# Phase 06 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Plan review | `docs/plans/phase-06-metrics-diagnostics/index.md` | State store & observability design review |
| ADR alignment | `docs/decisions/adr/005-state-management.md` | Azure Table Storage is the Phase 06 authoritative shared store; Redis is deferred to a separately approved optimization scope. |
| Implementation (partial) | `src/foundry_router/credit.py`, `src/foundry_router/health/`, `src/foundry_router/state/table.py`, `src/foundry_router/main.py`, `src/foundry_router/metrics/__init__.py` | `CreditStore`, `HealthStore`, in-memory health state, injected-client Azure Table health boundary, live `/admin/status` diagnostics, and Prometheus `/metrics` exporter |
| Focused tests | `tests/unit/test_credit.py`, `tests/unit/test_main.py`, `tests/unit/test_state.py` | Credit live snapshot, admin diagnostics, metrics format, protocol conformance, cooldown expiry, disabled-state preservation, and adapter reset assertions |
| Full verification | `.venv/bin/python -m pytest` | Full repository test suite completed after Phase 06 partial implementation |
